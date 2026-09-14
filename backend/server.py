from dotenv import load_dotenv
load_dotenv()
import json
import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent import meeting_agent
from app.database import (
    calculate_project_risk,
    create_activity,
    create_contact,
    create_followup,
    create_meeting,
    create_task_meeting,
    ensure_followup_tables,
    ensure_task_meeting_tables,
    generate_followups_from_tasks,
    get_all_activities,
    get_all_tasks,
    get_decisions,
    get_dependencies,
    get_followups,
    get_meeting_participants,
    get_people,
    get_task_meetings,
    get_tasks_for_meeting,
    get_user,
    initialise_database,
    resolve_decision,
    update_followup_status,
    update_task_meeting_status,
    update_task_record,
    update_user,
)
from app.tools import reset_current_meeting, set_current_meeting


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


initialise_database()
ensure_followup_tables()
ensure_task_meeting_tables()


app = FastAPI(
    title="MicroManager API",
    description="Meeting-to-execution backend",
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MeetingRequest(BaseModel):
    transcript: str


class UserUpdateRequest(BaseModel):
    name: str
    email: str
    role: str


class ContactRequest(BaseModel):
    name: str
    email: str = ""
    contact_type: str = "External guest"


class TaskUpdateRequest(BaseModel):
    owner: str
    deadline: str
    status: str


class TaskMeetingRequest(BaseModel):
    task_id: int
    title: str
    meeting_link: str
    scheduled_at: str


def clean_text_for_agent(text):
    return (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("—", "-")
        .replace("–", "-")
        .replace("…", "...")
    )


@app.get("/")
def home():
    return {
        "message": "MicroManager backend is running",
        "version": "2.0.0",
        "database": "connected",
    }


@app.post("/process-meeting")
def process_meeting(request: MeetingRequest):
    transcript = clean_text_for_agent(request.transcript.strip())

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="Transcript cannot be empty.",
        )

    meeting_id = create_meeting(transcript)
    token = set_current_meeting(meeting_id)

    current_tasks = get_all_tasks()[:50]

    compact_state = [
        {
            "id": task["id"],
            "task": task["task"],
            "owner": task["owner"],
            "deadline": task["deadline"],
            "status": task["status"],
        }
        for task in current_tasks
    ]

    prompt = (
        "CURRENT PROJECT STATE:\n"
        + json.dumps(compact_state, separators=(",", ":"))
        + "\n\nNEW MEETING OR STATUS UPDATE:\n"
        + transcript
    )

    try:
        meeting_agent(prompt)

        created_followups = generate_followups_from_tasks()

        if created_followups > 0:
            create_activity(
                "followups_generated",
                "Follow-ups generated",
                f"MicroManager automatically created {created_followups} follow-up draft(s).",
            )

        risk = calculate_project_risk()

        create_activity(
            "risk_recalculated",
            "Project risk recalculated",
            f"Project risk is now {risk['level']} with score {risk['score']}/100.",
        )

        tasks = get_tasks_for_meeting(meeting_id)

        create_activity(
            "meeting_processed",
            "Meeting processed",
            f"Meeting {meeting_id} processed; {len(tasks)} new task(s) created.",
        )

        return {
            "meeting_id": meeting_id,
            "tasks": tasks,
            "all_tasks": get_all_tasks(),
            "activities": get_all_activities(),
            "dependencies": get_dependencies(),
            "decisions": get_decisions(),
            "risk": risk,
            "participants": get_meeting_participants(meeting_id),
            "people": get_people(),
            "followups": get_followups(),
            "task_meetings": get_task_meetings(),
        }

    except Exception as error:
        create_activity(
            "meeting_error",
            "Meeting processing failed",
            str(error),
        )

        raise HTTPException(
            status_code=500,
            detail=f"Meeting processing failed: {error}",
        )

    finally:
        reset_current_meeting(token)


@app.get("/dashboard")
def dashboard():
    return {
        "tasks": get_all_tasks(),
        "activities": get_all_activities(),
        "dependencies": get_dependencies(),
        "decisions": get_decisions(),
        "risk": calculate_project_risk(),
        "participants": get_meeting_participants(),
        "people": get_people(),
        "user": get_user(1),
        "followups": get_followups(),
        "task_meetings": get_task_meetings(),
    }


@app.get("/tasks")
def tasks():
    return {
        "tasks": get_all_tasks(),
    }


@app.put("/tasks/{task_id}")
def update_task(task_id: int, request: TaskUpdateRequest):
    updated_task = update_task_record(
        task_id=task_id,
        owner=request.owner,
        deadline=request.deadline,
        status=request.status,
    )

    if updated_task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found.",
        )

    created_followups = generate_followups_from_tasks()
    risk = calculate_project_risk()

    create_activity(
        "task_updated",
        "Task updated manually",
        f"{updated_task['task']} is now assigned to {updated_task['owner']} with status {updated_task['status']}.",
    )

    if created_followups > 0:
        create_activity(
            "followups_generated",
            "Follow-ups generated",
            f"MicroManager created {created_followups} new follow-up draft(s).",
        )

    create_activity(
        "risk_recalculated",
        "Project risk recalculated",
        f"Project risk is now {risk['level']} with score {risk['score']}/100.",
    )

    return {
        "task": updated_task,
        "tasks": get_all_tasks(),
        "activities": get_all_activities(),
        "risk": risk,
        "followups": get_followups(),
    }


@app.get("/activities")
def activities():
    return {
        "activities": get_all_activities(),
    }


@app.get("/dependencies")
def dependencies():
    return {
        "dependencies": get_dependencies(),
    }


@app.get("/participants")
def participants(meeting_id: int | None = None):
    return {
        "participants": get_meeting_participants(meeting_id),
    }


@app.get("/people")
def people():
    return get_people()


@app.post("/contacts")
def add_contact(request: ContactRequest):
    name = request.name.strip()
    email = request.email.strip()
    contact_type = request.contact_type.strip() or "External guest"

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Contact name is required.",
        )

    contact = create_contact(
        name=name,
        email=email,
        contact_type=contact_type,
    )

    create_activity(
        "contact_created",
        "Contact added",
        f"{contact['name']} was added to People.",
    )

    return {
        "contact": contact,
        "people": get_people(),
        "activities": get_all_activities(),
    }


@app.get("/decisions")
def decisions():
    return {
        "decisions": get_decisions(),
    }


@app.put("/decisions/{decision_id}/resolve")
def resolve(decision_id: int):
    resolve_decision(decision_id)

    create_activity(
        "decision_resolved",
        "Decision resolved",
        f"Decision {decision_id} resolved.",
    )

    risk = calculate_project_risk()

    create_activity(
        "risk_recalculated",
        "Project risk recalculated",
        f"Project risk is now {risk['level']} with score {risk['score']}/100.",
    )

    return {
        "resolved": True,
        "decision_id": decision_id,
        "decisions": get_decisions(),
        "risk": risk,
    }


@app.get("/risk")
def risk():
    return {
        "risk": calculate_project_risk(),
    }


@app.get("/followups")
def followups():
    return {
        "followups": get_followups(),
    }


@app.post("/followups/generate")
def generate_followups():
    created = generate_followups_from_tasks()

    create_activity(
        "followups_generated",
        "Follow-ups generated",
        f"MicroManager created {created} follow-up draft(s).",
    )

    return {
        "created": created,
        "followups": get_followups(),
        "activities": get_all_activities(),
    }


@app.put("/followups/{followup_id}/status")
def update_followup(followup_id: int, status: str):
    update_followup_status(
        followup_id,
        status,
    )

    create_activity(
        "followup_updated",
        "Follow-up updated",
        f"Follow-up {followup_id} marked as {status}.",
    )

    return {
        "updated": True,
        "followups": get_followups(),
        "activities": get_all_activities(),
    }


@app.get("/task-meetings")
def task_meetings():
    return {
        "task_meetings": get_task_meetings(),
    }


@app.post("/task-meetings")
def schedule_task_meeting(request: TaskMeetingRequest):
    title = request.title.strip()
    meeting_link = request.meeting_link.strip()
    scheduled_at = request.scheduled_at.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Meeting title is required.",
        )

    if not meeting_link:
        raise HTTPException(
            status_code=400,
            detail="Meeting link is required.",
        )

    if not scheduled_at:
        raise HTTPException(
            status_code=400,
            detail="Meeting time is required.",
        )

    task_meeting_id = create_task_meeting(
        request.task_id,
        title,
        meeting_link,
        scheduled_at,
    )

    create_followup(
        request.task_id,
        "Meeting reminder",
        f"Reminder: '{title}' is scheduled for {scheduled_at}. Join here: {meeting_link}",
        "Meeting reminder",
    )

    create_activity(
        "meeting_scheduled",
        "Task meeting scheduled",
        f"MicroManager scheduled '{title}' and created a meeting reminder.",
    )

    return {
        "scheduled": True,
        "task_meeting_id": task_meeting_id,
        "task_meetings": get_task_meetings(),
        "followups": get_followups(),
        "activities": get_all_activities(),
    }


@app.put("/task-meetings/{task_meeting_id}/status")
def update_task_meeting(task_meeting_id: int, status: str):
    update_task_meeting_status(
        task_meeting_id,
        status,
    )

    create_activity(
        "task_meeting_updated",
        "Task meeting updated",
        f"Meeting {task_meeting_id} marked as {status}.",
    )

    return {
        "updated": True,
        "task_meetings": get_task_meetings(),
        "activities": get_all_activities(),
    }


@app.get("/users/me")
def current_user():
    user = get_user(1)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    return {
        "user": user,
    }


@app.put("/users/me")
def save_user(request: UserUpdateRequest):
    name = request.name.strip()
    email = request.email.strip()
    role = request.role.strip() or "Team member"

    if not name or not email:
        raise HTTPException(
            status_code=400,
            detail="Name and email are required.",
        )

    user = update_user(
        1,
        name,
        email,
        role,
    )

    create_activity(
        "profile_updated",
        "Profile updated",
        f"{user['name']}'s profile changed.",
    )

    return {
        "user": user,
    }