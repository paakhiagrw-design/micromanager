import json
import os
import re
import ssl
import urllib.error
import urllib.request

from app.tools import save_project_analysis


SYSTEM_PROMPT = """
You are MicroManager, an autonomous meeting-to-execution agent.

You receive:
1. CURRENT PROJECT STATE
2. NEW MEETING OR STATUS UPDATE

Your job is to understand the transcript and update the project automatically.

Return ONLY valid JSON.
Do not use markdown.
Do not explain anything.
Do not write text before or after the JSON.

IMPORTANT BEHAVIOUR:
- If the work already exists in CURRENT PROJECT STATE, update it.
- Do not create duplicate tasks if the task already exists.
- If someone says a task is finished, completed, shipped, done, wrapped, or ready, mark it as Done.
- If someone says a task is blocked, waiting, stuck, delayed by another task, or depends on unfinished work, mark it as Blocked.
- If someone says they need more time, moved a deadline, pushed a date, or changed a previous commitment, update the deadline and add a contradiction.
- If someone takes ownership of unassigned work, update the owner.
- If someone says nobody owns something, create or update it with owner Unassigned.
- If a human choice is needed, create a decision.
- If one task depends on another, create a dependency.
- Keep all wording short and dashboard-friendly.

HOW TO MATCH EXISTING TASKS:
- Match by meaning, not exact wording.
- "login", "authentication", "auth", "registration API" may refer to the same task.
- "database", "SQLite", "DB setup", "task deadlines from database" may refer to the same task.
- "follow-up queue", "followups", "reminders queue" may refer to the same task.
- "project risk", "risk dashboard", "risk page" may refer to the same task.
- "tasks page", "task assignment", "execution board" may refer to the same task.

Return this exact JSON shape:

{
  "meeting_notes": "short useful notes",
  "participants": [
    {
      "name": "Person name",
      "email": "",
      "confidence": 0.9
    }
  ],
  "new_tasks": [
    {
      "task": "Task name",
      "owner": "Owner name or Unassigned",
      "deadline": "Deadline or No deadline",
      "status": "Open"
    }
  ],
  "task_updates": [
    {
      "task_id": null,
      "task": "Existing task name",
      "owner": null,
      "deadline": null,
      "status": "Open/In Progress/Blocked/Done",
      "reason": "Why this changed"
    }
  ],
  "dependencies": [
    {
      "task_id": null,
      "task": "Dependent task",
      "depends_on_task_id": null,
      "depends_on": "Blocking task",
      "description": "Why this depends on that"
    }
  ],
  "contradictions": [
    {
      "task_id": null,
      "task": "Existing task",
      "description": "What changed",
      "old_value": "Old commitment",
      "new_value": "New commitment"
    }
  ],
  "decisions": [
    {
      "title": "Decision needed",
      "description": "What human needs to decide",
      "priority": "Low/Medium/High"
    }
  ]
}
"""


def get_api_key():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Gemini API key is missing. Set GEMINI_API_KEY before processing meetings."
        )

    return api_key


def extract_json(text):
    if not text:
        raise RuntimeError("Gemini returned an empty response.")

    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "")
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.strip()

    decoder = json.JSONDecoder()
    start = cleaned.find("{")

    if start == -1:
        raise RuntimeError(
            "Gemini did not return JSON. Raw response: " + cleaned[:500]
        )

    try:
        parsed, end = decoder.raw_decode(cleaned[start:])
        return json.dumps(parsed)
    except json.JSONDecodeError:
        pass

    matches = re.findall(r"\{[\s\S]*?\}", cleaned)

    for match in matches:
        try:
            parsed = json.loads(match)
            return json.dumps(parsed)
        except json.JSONDecodeError:
            continue

    raise RuntimeError(
        "Gemini returned broken JSON. Raw response: " + cleaned[:500]
    )


def get_available_models(api_key, context):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models?key="
        + api_key
    )

    request = urllib.request.Request(
        url,
        headers={
            "Content-Type": "application/json",
        },
        method="GET",
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
        context=context,
    ) as response:
        data = json.loads(response.read().decode("utf-8"))

    models = []

    for model in data.get("models", []):
        name = model.get("name", "")
        methods = model.get("supportedGenerationMethods", [])

        if name.startswith("models/") and "generateContent" in methods:
            models.append(name.replace("models/", ""))

    preferred = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]

    ordered = []

    for model in preferred:
        if model in models:
            ordered.append(model)

    for model in models:
        if model not in ordered:
            ordered.append(model)

    return ordered


def call_gemini(prompt):
    api_key = get_api_key()
    context = ssl._create_unverified_context()

    models_to_try = []

    env_model = os.getenv("GEMINI_MODEL", "").strip()
    if env_model:
        models_to_try.append(env_model)

    models_to_try.extend(
        get_available_models(
            api_key,
            context,
        )
    )

    if not models_to_try:
        raise RuntimeError("No Gemini models available for this API key.")

    last_error = None

    for model in models_to_try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + model
            + ":generateContent?key="
            + api_key
        )

        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": SYSTEM_PROMPT + "\n\n" + prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1800,
            },
        }

        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=60,
                context=context,
            ) as response:
                data = json.loads(response.read().decode("utf-8"))

            candidates = data.get("candidates", [])

            if not candidates:
                raise RuntimeError("Gemini returned no candidates.")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            if not parts:
                raise RuntimeError("Gemini returned no text parts.")

            text = parts[0].get("text", "")

            if not text:
                raise RuntimeError("Gemini text response was empty.")

            return text

        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8")
            last_error = f"{model}: {details}"

        except Exception as error:
            last_error = f"{model}: {error}"

    raise RuntimeError(
        f"Gemini request failed. Last error: {last_error}"
    )


def normalise_list(value):
    if isinstance(value, list):
        return value

    return []


def clean_analysis(analysis):
    return {
        "meeting_notes": analysis.get("meeting_notes", ""),
        "participants": normalise_list(analysis.get("participants")),
        "new_tasks": normalise_list(analysis.get("new_tasks")),
        "task_updates": normalise_list(analysis.get("task_updates")),
        "dependencies": normalise_list(analysis.get("dependencies")),
        "contradictions": normalise_list(analysis.get("contradictions")),
        "decisions": normalise_list(analysis.get("decisions")),
    }


def meeting_agent(prompt):
    response_text = call_gemini(prompt)
    json_text = extract_json(response_text)
    analysis = json.loads(json_text)
    safe_analysis = clean_analysis(analysis)

    save_project_analysis(
        json.dumps(
            safe_analysis,
            ensure_ascii=False,
        )
    )

    return safe_analysis