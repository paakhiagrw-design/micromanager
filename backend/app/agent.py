import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from app.tools import save_project_analysis


SYSTEM_PROMPT = """
You are MicroManager, an autonomous meeting-to-execution agent.

You receive:
1. CURRENT PROJECT STATE
2. NEW MEETING OR STATUS UPDATE

Analyse the meeting and update the project state.

Rules:
- Match existing tasks by meaning, not exact wording.
- Never create duplicate tasks.
- Finished, completed, shipped, done, wrapped or ready means Done.
- Blocked, waiting, stuck or dependent on unfinished work means Blocked.
- If a deadline changes, update it and create a contradiction.
- If someone accepts responsibility, assign the task to them.
- If nobody owns a task, use Unassigned.
- Create a decision only when human judgement is required.
- Create dependencies when one task requires another task.
- Keep all wording short and dashboard-friendly.

Return only one valid JSON object.
Do not return markdown, explanations or code fences.

Use this exact structure:

{
  "meeting_notes": "Short summary",
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
      "status": "Open",
      "reason": "Reason for change"
    }
  ],
  "dependencies": [
    {
      "task_id": null,
      "task": "Dependent task",
      "depends_on_task_id": null,
      "depends_on": "Blocking task",
      "description": "Dependency explanation"
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
      "description": "What must be decided",
      "priority": "Low"
    }
  ]
}

Every top-level field must be included.
Use empty arrays when nothing is detected.
"""


def get_api_key():
    api_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )

    if not api_key:
        raise RuntimeError(
            "Gemini API key is missing. "
            "Set GEMINI_API_KEY in Render."
        )

    return api_key.strip()


def get_ssl_context():
    return ssl.create_default_context()


def send_request(url, method="GET", body=None, timeout=60):
    headers = {
        "Content-Type": "application/json"
    }

    request_data = None

    if body is not None:
        request_data = json.dumps(body).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=request_data,
        headers=headers,
        method=method
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
        context=get_ssl_context()
    ) as response:
        response_text = response.read().decode("utf-8")
        return json.loads(response_text)


def get_available_models(api_key):
    encoded_key = urllib.parse.quote(api_key)

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models?key={encoded_key}"
    )

    data = send_request(
        url=url,
        method="GET",
        timeout=30
    )

    available_models = []

    for model in data.get("models", []):
        name = model.get("name", "")
        methods = model.get(
            "supportedGenerationMethods",
            []
        )

        if (
            name.startswith("models/")
            and "generateContent" in methods
        ):
            available_models.append(
                name.replace("models/", "")
            )

    return available_models


def choose_models(api_key):
    available_models = get_available_models(api_key)

    preferred_models = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite"
    ]

    chosen_models = []

    environment_model = os.getenv(
        "GEMINI_MODEL",
        ""
    ).strip()

    environment_model = environment_model.replace(
        "models/",
        ""
    )

    if environment_model:
        chosen_models.append(environment_model)

    for model in preferred_models:
        if (
            model in available_models
            and model not in chosen_models
        ):
            chosen_models.append(model)

    for model in available_models:
        if (
            "gemini" in model.lower()
            and model not in chosen_models
        ):
            chosen_models.append(model)

    if not chosen_models:
        raise RuntimeError(
            "No Gemini generateContent models are "
            "available for this API key."
        )

    return chosen_models


def extract_response_text(response_data):
    candidates = response_data.get("candidates", [])

    if not candidates:
        prompt_feedback = response_data.get(
            "promptFeedback",
            {}
        )

        raise RuntimeError(
            "Gemini returned no candidates. "
            f"Prompt feedback: {prompt_feedback}"
        )

    content = candidates[0].get("content", {})
    parts = content.get("parts", [])

    if not parts:
        raise RuntimeError(
            "Gemini returned no response parts."
        )

    answer_parts = []

    for part in parts:
        text = part.get("text", "")

        if not text:
            continue

        # Gemini 2.5 may include an internal thinking part.
        # Do not treat that part as the final JSON response.
        if part.get("thought") is True:
            continue

        answer_parts.append(text)

    if not answer_parts:
        answer_parts = [
            part.get("text", "")
            for part in parts
            if part.get("text")
        ]

    response_text = "\n".join(answer_parts).strip()

    if not response_text:
        raise RuntimeError(
            "Gemini returned an empty text response."
        )

    return response_text


def extract_json(text):
    if not text:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    cleaned = text.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    ).strip()

    try:
        parsed = json.loads(cleaned)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    possible_objects = []

    for index, character in enumerate(cleaned):
        if character != "{":
            continue

        try:
            parsed, _ = decoder.raw_decode(
                cleaned[index:]
            )

            if isinstance(parsed, dict):
                possible_objects.append(parsed)

        except json.JSONDecodeError:
            continue

    expected_fields = {
        "meeting_notes",
        "participants",
        "new_tasks",
        "task_updates",
        "dependencies",
        "contradictions",
        "decisions"
    }

    for possible_object in reversed(possible_objects):
        if expected_fields.intersection(
            possible_object.keys()
        ):
            return possible_object

    raise RuntimeError(
        "Gemini did not return usable JSON. "
        f"Raw response: {cleaned[:500]}"
    )


def call_gemini(prompt):
    api_key = get_api_key()
    models = choose_models(api_key)
    encoded_key = urllib.parse.quote(api_key)

    last_error = None

    for model in models:
        encoded_model = urllib.parse.quote(
            model,
            safe="-_."
        )

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{encoded_model}:generateContent"
            f"?key={encoded_key}"
        )

        body = {
            "system_instruction": {
                "parts": [
                    {
                        "text": SYSTEM_PROMPT
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json"
            }
        }

        try:
            response_data = send_request(
                url=url,
                method="POST",
                body=body,
                timeout=90
            )

            return extract_response_text(
                response_data
            )

        except urllib.error.HTTPError as error:
            try:
                error_details = (
                    error.read()
                    .decode("utf-8")
                )
            except Exception:
                error_details = str(error)

            last_error = (
                f"{model}: HTTP {error.code}: "
                f"{error_details}"
            )

        except urllib.error.URLError as error:
            last_error = (
                f"{model}: connection error: "
                f"{error.reason}"
            )

        except Exception as error:
            last_error = f"{model}: {error}"

    raise RuntimeError(
        "Gemini request failed. "
        f"Last error: {last_error}"
    )


def normalise_list(value):
    if isinstance(value, list):
        return value

    return []


def clean_analysis(analysis):
    if not isinstance(analysis, dict):
        raise RuntimeError(
            "Gemini analysis was not a JSON object."
        )

    return {
        "meeting_notes": str(
            analysis.get("meeting_notes", "")
        ),
        "participants": normalise_list(
            analysis.get("participants")
        ),
        "new_tasks": normalise_list(
            analysis.get("new_tasks")
        ),
        "task_updates": normalise_list(
            analysis.get("task_updates")
        ),
        "dependencies": normalise_list(
            analysis.get("dependencies")
        ),
        "contradictions": normalise_list(
            analysis.get("contradictions")
        ),
        "decisions": normalise_list(
            analysis.get("decisions")
        )
    }


def meeting_agent(prompt):
    if not prompt or not prompt.strip():
        raise RuntimeError(
            "Meeting transcript cannot be empty."
        )

    response_text = call_gemini(prompt)
    analysis = extract_json(response_text)
    safe_analysis = clean_analysis(analysis)

    save_project_analysis(
        json.dumps(
            safe_analysis,
            ensure_ascii=False
        )
    )

    return safe_analysis