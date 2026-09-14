import sqlite3
from datetime import date
from datetime import datetime
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent.parent / "micromanager.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _rows(cursor):
    return [dict(row) for row in cursor.fetchall()]


def initialise_database():
    connection = get_connection()
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'Team member',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transcript TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER,
            task TEXT NOT NULL,
            owner TEXT NOT NULL DEFAULT 'Unassigned',
            deadline TEXT NOT NULL DEFAULT 'No deadline',
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            depends_on_task_id INTEGER NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(task_id, depends_on_task_id),
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS contradictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER,
            task_id INTEGER,
            description TEXT NOT NULL,
            old_value TEXT NOT NULL DEFAULT '',
            new_value TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE SET NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'Medium',
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_by_user_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            contact_type TEXT NOT NULL DEFAULT 'External guest',
            linked_user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(created_by_user_id, name, email),
            FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (linked_user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS meeting_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            detected_name TEXT NOT NULL,
            detected_email TEXT NOT NULL DEFAULT '',
            user_id INTEGER,
            contact_id INTEGER,
            match_status TEXT NOT NULL DEFAULT 'Unmatched',
            confidence REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(meeting_id, detected_name),
            FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL
        );

        INSERT OR IGNORE INTO users (id, name, email, role)
        VALUES (1, 'User', 'user@example.com', 'Team member');
        """
    )

    for table, column, definition in [
        ("meetings", "notes", "TEXT NOT NULL DEFAULT ''"),
        ("tasks", "updated_at", "TEXT NOT NULL DEFAULT ''"),
        ("tasks", "owner_user_id", "INTEGER"),
        ("tasks", "owner_contact_id", "INTEGER"),
    ]:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})")
        }

        if column not in columns:
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )

    connection.execute(
        "UPDATE tasks SET updated_at = created_at WHERE updated_at = ''"
    )

    connection.commit()
    connection.close()


def _normalise_person_name(name):
    return " ".join((name or "").strip().lower().split())


def resolve_meeting_participant(meeting_id, name, email="", confidence=0.8):
    clean_name = " ".join((name or "").strip().split())
    clean_email = (email or "").strip().lower()

    if not clean_name:
        return None

    target = _normalise_person_name(clean_name)

    connection = get_connection()

    user_matches = _rows(
        connection.execute(
            """
            SELECT *
            FROM users
            WHERE lower(trim(name)) = ?
               OR (? != '' AND lower(email) = ?)
            """,
            (target, clean_email, clean_email),
        )
    )

    contact_matches = _rows(
        connection.execute(
            """
            SELECT *
            FROM contacts
            WHERE lower(trim(name)) = ?
               OR (? != '' AND lower(email) = ?)
            """,
            (target, clean_email, clean_email),
        )
    )

    user_id = None
    contact_id = None
    status = "Unmatched"
    total_matches = len(user_matches) + len(contact_matches)

    if total_matches == 1 and user_matches:
        user_id = user_matches[0]["id"]
        status = "Account matched"
        confidence = max(float(confidence or 0), 0.95)

    elif total_matches == 1 and contact_matches:
        contact_id = contact_matches[0]["id"]
        status = "External guest"
        confidence = max(float(confidence or 0), 0.9)

    elif total_matches > 1:
        status = "Ambiguous"
        confidence = min(float(confidence or 0), 0.5)

    else:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO contacts (name, email, contact_type)
            VALUES (?, ?, 'External guest')
            """,
            (clean_name, clean_email),
        )

        contact_id = cursor.lastrowid

        if not contact_id:
            row = connection.execute(
                """
                SELECT id
                FROM contacts
                WHERE created_by_user_id = 1
                  AND name = ?
                  AND email = ?
                """,
                (clean_name, clean_email),
            ).fetchone()

            contact_id = row["id"] if row else None

        status = "External guest"
        confidence = max(float(confidence or 0), 0.75)

    connection.execute(
        """
        INSERT INTO meeting_participants
        (
            meeting_id,
            detected_name,
            detected_email,
            user_id,
            contact_id,
            match_status,
            confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(meeting_id, detected_name) DO UPDATE SET
            detected_email = excluded.detected_email,
            user_id = excluded.user_id,
            contact_id = excluded.contact_id,
            match_status = excluded.match_status,
            confidence = excluded.confidence
        """,
        (
            meeting_id,
            clean_name,
            clean_email,
            user_id,
            contact_id,
            status,
            confidence,
        ),
    )

    connection.commit()

    row = connection.execute(
        """
        SELECT
            mp.*,
            COALESCE(u.name, c.name, mp.detected_name) AS display_name,
            COALESCE(u.email, c.email, mp.detected_email) AS display_email
        FROM meeting_participants mp
        LEFT JOIN users u ON u.id = mp.user_id
        LEFT JOIN contacts c ON c.id = mp.contact_id
        WHERE mp.meeting_id = ?
          AND mp.detected_name = ?
        """,
        (meeting_id, clean_name),
    ).fetchone()

    connection.close()

    return dict(row)


def get_meeting_participants(meeting_id=None):
    connection = get_connection()

    query = """
        SELECT
            mp.*,
            COALESCE(u.name, c.name, mp.detected_name) AS display_name,
            COALESCE(u.email, c.email, mp.detected_email) AS display_email
        FROM meeting_participants mp
        LEFT JOIN users u ON u.id = mp.user_id
        LEFT JOIN contacts c ON c.id = mp.contact_id
    """

    if meeting_id is None:
        rows = _rows(
            connection.execute(
                query + " ORDER BY mp.id DESC"
            )
        )
    else:
        rows = _rows(
            connection.execute(
                query + " WHERE mp.meeting_id = ? ORDER BY mp.id",
                (meeting_id,),
            )
        )

    connection.close()

    return rows


def get_people():
    connection = get_connection()

    users = _rows(
        connection.execute(
            """
            SELECT id, name, email, role
            FROM users
            ORDER BY lower(name)
            """
        )
    )

    contacts = _rows(
        connection.execute(
            """
            SELECT id, name, email, contact_type, linked_user_id
            FROM contacts
            ORDER BY lower(name)
            """
        )
    )

    connection.close()

    return {
        "accounts": users,
        "external_guests": contacts,
    }


def link_task_owners_for_meeting(meeting_id):
    connection = get_connection()

    connection.execute(
        """
        UPDATE tasks
        SET owner_user_id = (
                SELECT mp.user_id
                FROM meeting_participants mp
                WHERE mp.meeting_id = tasks.meeting_id
                  AND lower(trim(mp.detected_name)) = lower(trim(tasks.owner))
                LIMIT 1
            ),
            owner_contact_id = (
                SELECT mp.contact_id
                FROM meeting_participants mp
                WHERE mp.meeting_id = tasks.meeting_id
                  AND lower(trim(mp.detected_name)) = lower(trim(tasks.owner))
                LIMIT 1
            )
        WHERE meeting_id = ?
        """,
        (meeting_id,),
    )

    connection.commit()
    connection.close()


def create_meeting(transcript):
    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO meetings (transcript)
        VALUES (?)
        """,
        (transcript,),
    )

    meeting_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return meeting_id


def update_meeting_notes(meeting_id, notes):
    connection = get_connection()

    connection.execute(
        """
        UPDATE meetings
        SET notes = ?
        WHERE id = ?
        """,
        (notes, meeting_id),
    )

    connection.commit()
    connection.close()


def create_task_record(task, owner, deadline, meeting_id=None, status="Open"):
    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO tasks (meeting_id, task, owner, deadline, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            meeting_id,
            task,
            owner or "Unassigned",
            deadline or "No deadline",
            status,
        ),
    )

    task_id = cursor.lastrowid

    row = connection.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    connection.commit()
    connection.close()

    return dict(row)


def update_task_record(task_id, deadline=None, status=None, owner=None):
    connection = get_connection()

    current = connection.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    if current is None:
        connection.close()
        return None

    connection.execute(
        """
        UPDATE tasks
        SET deadline = ?,
            status = ?,
            owner = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            deadline or current["deadline"],
            status or current["status"],
            owner or current["owner"],
            task_id,
        ),
    )

    updated = connection.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    connection.commit()
    connection.close()

    return dict(updated)


def find_task(task_id=None, task_name=None):
    connection = get_connection()

    if task_id:
        row = connection.execute(
            """
            SELECT *
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT *
            FROM tasks
            WHERE lower(task) = lower(?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (task_name or "",),
        ).fetchone()

    connection.close()

    return dict(row) if row else None


def get_all_tasks():
    connection = get_connection()

    tasks = _rows(
        connection.execute(
            """
            SELECT *
            FROM tasks
            ORDER BY id DESC
            """
        )
    )

    connection.close()

    return tasks


def get_tasks_for_meeting(meeting_id):
    connection = get_connection()

    tasks = _rows(
        connection.execute(
            """
            SELECT *
            FROM tasks
            WHERE meeting_id = ?
            ORDER BY id
            """,
            (meeting_id,),
        )
    )

    connection.close()

    return tasks


def create_dependency(task_id, depends_on_task_id, description=""):
    if task_id == depends_on_task_id:
        return None

    connection = get_connection()

    connection.execute(
        """
        INSERT OR IGNORE INTO dependencies
        (task_id, depends_on_task_id, description)
        VALUES (?, ?, ?)
        """,
        (task_id, depends_on_task_id, description),
    )

    connection.commit()
    connection.close()


def get_dependencies():
    connection = get_connection()

    dependencies = _rows(
        connection.execute(
            """
            SELECT
                d.*,
                t.task AS task,
                blocker.task AS depends_on_task,
                blocker.status AS blocker_status
            FROM dependencies d
            JOIN tasks t ON t.id = d.task_id
            JOIN tasks blocker ON blocker.id = d.depends_on_task_id
            ORDER BY d.id DESC
            """
        )
    )

    connection.close()

    return dependencies


def create_contradiction(meeting_id, task_id, description, old_value="", new_value=""):
    connection = get_connection()

    connection.execute(
        """
        INSERT INTO contradictions
        (meeting_id, task_id, description, old_value, new_value)
        VALUES (?, ?, ?, ?, ?)
        """,
        (meeting_id, task_id, description, old_value, new_value),
    )

    connection.commit()
    connection.close()


def create_decision(meeting_id, title, description, priority="Medium"):
    connection = get_connection()

    connection.execute(
        """
        INSERT INTO decisions (meeting_id, title, description, priority)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, title, description, priority),
    )

    connection.commit()
    connection.close()


def get_decisions():
    connection = get_connection()

    decisions = _rows(
        connection.execute(
            """
            SELECT *
            FROM decisions
            WHERE status = 'Open'
            ORDER BY id DESC
            """
        )
    )

    connection.close()

    return decisions


def resolve_decision(decision_id):
    connection = get_connection()

    connection.execute(
        """
        UPDATE decisions
        SET status = 'Resolved'
        WHERE id = ?
        """,
        (decision_id,),
    )

    connection.commit()
    connection.close()


def create_activity(activity_type, title, description):
    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO activities (activity_type, title, description)
        VALUES (?, ?, ?)
        """,
        (activity_type, title, description),
    )

    connection.commit()
    connection.close()

    return cursor.lastrowid


def get_all_activities():
    connection = get_connection()

    activities = _rows(
        connection.execute(
            """
            SELECT *
            FROM activities
            ORDER BY id DESC
            LIMIT 100
            """
        )
    )

    connection.close()

    return activities


def get_user(user_id=1):
    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    connection.close()

    return dict(row) if row else None


def update_user(user_id, name, email, role):
    connection = get_connection()

    connection.execute(
        """
        UPDATE users
        SET name = ?,
            email = ?,
            role = ?
        WHERE id = ?
        """,
        (name, email, role, user_id),
    )

    connection.commit()
    connection.close()

    return get_user(user_id)


def calculate_project_risk():
    tasks = get_all_tasks()
    dependencies = get_dependencies()
    decisions = get_decisions()

    score = 100
    signals = []

    blocked_tasks = 0
    unassigned_tasks = 0
    overdue_tasks = 0
    due_soon_tasks = 0
    blocked_dependencies = 0
    open_decisions = 0

    today = datetime.now().date()

    for task in tasks:
        status = (task.get("status") or "").lower()
        owner = (task.get("owner") or "").strip()
        deadline = task.get("deadline") or ""

        if status == "blocked":
            blocked_tasks += 1

        if owner == "" or owner.lower() == "unassigned":
            unassigned_tasks += 1

        if "T" in deadline:
            try:
                deadline_date = datetime.fromisoformat(deadline).date()

                if deadline_date < today and status != "done":
                    overdue_tasks += 1
                elif (deadline_date - today).days <= 2 and status != "done":
                    due_soon_tasks += 1
            except ValueError:
                pass

    for dependency in dependencies:
        blocker_status = (
            dependency.get("blocker_status") or ""
        ).lower()

        if blocker_status != "done":
            blocked_dependencies += 1

    for decision in decisions:
        status = (decision.get("status") or "").lower()

        if status != "Resolved".lower():
            open_decisions += 1

    score -= blocked_tasks * 12
    score -= unassigned_tasks * 8
    score -= overdue_tasks * 15
    score -= due_soon_tasks * 6
    score -= blocked_dependencies * 10
    score -= open_decisions * 10

    score = max(score, 0)

    if blocked_tasks:
        signals.append(f"{blocked_tasks} blocked task(s)")

    if unassigned_tasks:
        signals.append(f"{unassigned_tasks} unassigned task(s)")

    if overdue_tasks:
        signals.append(f"{overdue_tasks} overdue task(s)")

    if due_soon_tasks:
        signals.append(f"{due_soon_tasks} task(s) due soon")

    if blocked_dependencies:
        signals.append(f"{blocked_dependencies} dependency blocker(s)")

    if open_decisions:
        signals.append(f"{open_decisions} human decision(s) needed")

    if not signals:
        signals.append("No major risks detected")

    if score >= 80:
        level = "Low"
    elif score >= 50:
        level = "Medium"
    else:
        level = "High"

    return {
        "score": score,
        "level": level,
        "signals": signals,
        "blocked_tasks": blocked_tasks,
        "unassigned_tasks": unassigned_tasks,
        "overdue_tasks": overdue_tasks,
        "due_soon_tasks": due_soon_tasks,
        "blocked_dependencies": blocked_dependencies,
        "open_decisions": open_decisions,
    }


    tasks = get_all_tasks()
    dependencies = get_dependencies()
    decisions = get_decisions()

    unassigned = sum(
        1
        for task in tasks
        if task["owner"].strip().lower() in {"", "unassigned", "unknown"}
    )

    overdue = 0
    today = date.today().isoformat()

    for task in tasks:
        deadline = task["deadline"]

        if len(deadline) == 10 and deadline[4] == "-" and task["status"] != "Done":
            overdue += int(deadline < today)

    blocked = sum(
        1
        for dependency in dependencies
        if dependency["blocker_status"] != "Done"
    )

    score = max(
        0,
        100
        - unassigned * 10
        - overdue * 15
        - blocked * 6
        - len(decisions) * 15,
    )

    level = "Low" if score >= 80 else "Medium" if score >= 55 else "High"

    signals = []

    if overdue:
        signals.append(f"{overdue} overdue task(s)")

    if unassigned:
        signals.append(f"{unassigned} unassigned task(s)")

    if blocked:
        signals.append(f"{blocked} active dependency risk(s)")

    if decisions:
        signals.append(f"{len(decisions)} human decision(s) needed")

    if not signals:
        signals.append("No major risks detected")

    return {
        "score": score,
        "level": level,
        "signals": signals,
        "overdue_tasks": overdue,
        "unassigned_tasks": unassigned,
        "blocked_dependencies": blocked,
        "open_decisions": len(decisions),
    }

def create_contact(name, email="", contact_type="External guest"):
    clean_name = " ".join((name or "").strip().split())
    clean_email = (email or "").strip().lower()
    clean_type = contact_type.strip() or "External guest"

    if not clean_name:
        raise ValueError("Contact name is required.")

    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO contacts
        (created_by_user_id, name, email, contact_type)
        VALUES (1, ?, ?, ?)
        """,
        (clean_name, clean_email, clean_type),
    )

    contact_id = cursor.lastrowid

    if not contact_id:
        row = connection.execute(
            """
            SELECT id
            FROM contacts
            WHERE created_by_user_id = 1
              AND name = ?
              AND email = ?
            """,
            (clean_name, clean_email),
        ).fetchone()

        contact_id = row["id"] if row else None

    contact = connection.execute(
        """
        SELECT id, name, email, contact_type, linked_user_id, created_at
        FROM contacts
        WHERE id = ?
        """,
        (contact_id,),
    ).fetchone()

    connection.commit()
    connection.close()

    return dict(contact)

def ensure_followup_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            followup_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
        """
    )

    connection.commit()
    connection.close()


def create_followup(task_id, title, message, followup_type):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO followups (
            task_id,
            title,
            message,
            followup_type
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            task_id,
            title,
            message,
            followup_type,
        ),
    )

    connection.commit()
    followup_id = cursor.lastrowid
    connection.close()

    return followup_id


def get_followups():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            followups.id,
            followups.task_id,
            followups.title,
            followups.message,
            followups.followup_type,
            followups.status,
            followups.created_at,
            followups.updated_at,
            tasks.task,
            tasks.owner,
            tasks.deadline
        FROM followups
        LEFT JOIN tasks
        ON followups.task_id = tasks.id
        ORDER BY followups.id DESC
        """
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def update_followup_status(followup_id, status):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE followups
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            status,
            followup_id,
        ),
    )

    connection.commit()
    connection.close()


def followup_already_exists(task_id, followup_type):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM followups
        WHERE task_id = ?
        AND followup_type = ?
        LIMIT 1
        """,
        (
            task_id,
            followup_type,
        ),
    )

    row = cursor.fetchone()
    connection.close()

    return row is not None


def generate_followups_from_tasks():
    ensure_followup_tables()

    tasks = get_all_tasks()
    created = 0

    for task in tasks:
        task_id = task["id"]
        task_name = task["task"]
        owner = task["owner"] or "Unassigned"
        deadline = task["deadline"] or "No deadline"
        status = task["status"] or "Open"

        if owner == "Unassigned":
            if not followup_already_exists(task_id, "Unassigned owner"):
                create_followup(
                    task_id,
                    "Assign task owner",
                    f"The task '{task_name}' has no owner yet. Please assign someone before {deadline}.",
                    "Unassigned owner",
                )
                created += 1

        if status == "Blocked":
            if not followup_already_exists(task_id, "Blocked task"):
                create_followup(
                    task_id,
                    "Resolve blocked task",
                    f"The task '{task_name}' is blocked. Check with {owner} and decide what needs to happen next.",
                    "Blocked task",
                )
                created += 1

        if status in ["Open", "In Progress"] and deadline != "No deadline":
            if not followup_already_exists(task_id, "Deadline reminder"):
                create_followup(
                    task_id,
                    "Deadline reminder",
                    f"Reminder for {owner}: '{task_name}' is due by {deadline}. Please share a status update.",
                    "Deadline reminder",
                )
                created += 1

    return created
def ensure_task_meeting_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS task_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            meeting_link TEXT NOT NULL,
            scheduled_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
        """
    )

    connection.commit()
    connection.close()


def create_task_meeting(task_id, title, meeting_link, scheduled_at):
    ensure_task_meeting_tables()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO task_meetings (
            task_id,
            title,
            meeting_link,
            scheduled_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            task_id,
            title,
            meeting_link,
            scheduled_at,
        ),
    )

    connection.commit()
    meeting_id = cursor.lastrowid
    connection.close()

    return meeting_id


def get_task_meetings():
    ensure_task_meeting_tables()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            task_meetings.id,
            task_meetings.task_id,
            task_meetings.title,
            task_meetings.meeting_link,
            task_meetings.scheduled_at,
            task_meetings.status,
            task_meetings.created_at,
            task_meetings.updated_at,
            tasks.task,
            tasks.owner,
            tasks.deadline
        FROM task_meetings
        LEFT JOIN tasks
        ON task_meetings.task_id = tasks.id
        ORDER BY task_meetings.scheduled_at ASC
        """
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def update_task_meeting_status(task_meeting_id, status):
    ensure_task_meeting_tables()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE task_meetings
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            status,
            task_meeting_id,
        ),
    )

    connection.commit()
    connection.close()
