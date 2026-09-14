import json
from contextvars import ContextVar

from strands import tool

from app.database import (
    create_activity,
    create_contradiction,
    create_decision,
    create_dependency,
    create_task_record,
    find_task,
    link_task_owners_for_meeting,
    resolve_meeting_participant,
    update_meeting_notes,
    update_task_record,
)


current_meeting_id = ContextVar("current_meeting_id", default=None)


def set_current_meeting(meeting_id):
    return current_meeting_id.set(meeting_id)


def reset_current_meeting(token):
    current_meeting_id.reset(token)


def _task(reference):
    if not reference:
        return None

    return find_task(
        task_id=reference.get("task_id"),
        task_name=reference.get("task") or reference.get("task_name"),
    )


@tool
def save_project_analysis(analysis_json: str) -> dict:
    """Save one complete meeting or status-update analysis in a single batch."""

    meeting_id = current_meeting_id.get()
    analysis = json.loads(analysis_json)

    notes = analysis.get("meeting_notes", "")
    update_meeting_notes(meeting_id, notes)

    participants = []
    ambiguous_names = []

    for item in analysis.get("participants", []):
        participant = resolve_meeting_participant(
            meeting_id=meeting_id,
            name=item.get("name", ""),
            email=item.get("email", ""),
            confidence=item.get("confidence", 0.8),
        )

        if not participant:
            continue

        participants.append(participant)

        if participant["match_status"] == "Ambiguous":
            ambiguous_names.append(participant["detected_name"])

            create_decision(
                meeting_id,
                f'Which {participant["detected_name"]} attended?',
                "Multiple saved people have this name. Choose the correct account or guest.",
                "Medium",
            )

        elif participant["match_status"] == "External guest":
            create_activity(
                "participant_added",
                "External participant added",
                f'{participant["detected_name"]} was added from the meeting transcript.',
            )

    created_tasks = []

    for item in analysis.get("new_tasks", []):
        task = create_task_record(
            task=(item.get("task") or "Unknown task").strip(),
            owner=(item.get("owner") or "Unassigned").strip(),
            deadline=(item.get("deadline") or "No deadline").strip(),
            meeting_id=meeting_id,
            status=item.get("status") or "Open",
        )

        created_tasks.append(task)

        create_activity(
            "task_created",
            "Task created",
            f'{task["task"]} assigned to {task["owner"]} by {task["deadline"]}.',
        )

    updated_tasks = []

    for item in analysis.get("task_updates", []):
        existing = _task(item)

        if not existing:
            continue

        updated = update_task_record(
            existing["id"],
            deadline=item.get("deadline"),
            status=item.get("status"),
            owner=item.get("owner"),
        )

        updated_tasks.append(updated)

        create_activity(
            "task_updated",
            "Task updated",
            item.get("reason") or f'{existing["task"]} was updated.',
        )

    saved_dependencies = 0

    for item in analysis.get("dependencies", []):
        dependent = _task(
            {
                "task_id": item.get("task_id"),
                "task": item.get("task"),
            }
        )

        blocker = _task(
            {
                "task_id": item.get("depends_on_task_id"),
                "task": item.get("depends_on"),
            }
        )

        if dependent and blocker:
            create_dependency(
                dependent["id"],
                blocker["id"],
                item.get("description", ""),
            )

            saved_dependencies += 1

    for item in analysis.get("contradictions", []):
        task = _task(item)

        create_contradiction(
            meeting_id,
            task["id"] if task else None,
            item.get("description") or "A commitment changed.",
            item.get("old_value", ""),
            item.get("new_value", ""),
        )

        create_activity(
            "contradiction_detected",
            "Commitment changed",
            item.get("description") or "A previous commitment changed.",
        )

    for item in analysis.get("decisions", []):
        create_decision(
            meeting_id,
            item.get("title") or "Human decision needed",
            item.get("description") or "MicroManager needs human input.",
            item.get("priority") or "Medium",
        )

    link_task_owners_for_meeting(meeting_id)

    return {
        "saved": True,
        "new_tasks": len(created_tasks),
        "updated_tasks": len(updated_tasks),
        "dependencies": saved_dependencies,
        "contradictions": len(analysis.get("contradictions", [])),
        "decisions": len(analysis.get("decisions", [])),
        "participants": len(participants),
        "ambiguous_participants": ambiguous_names,
    }