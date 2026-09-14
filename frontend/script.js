if (localStorage.getItem("microManagerLoggedIn") !== "true") {
    window.location.href = "login.html";
}

const API_URL = "https://micromanager-exsv.onrender.com";
const transcriptInput = document.getElementById("transcript");
const processButton = document.getElementById("processButton");
const processingState = document.getElementById("processing");
const resultsSection = document.getElementById("results");
const characterCount = document.getElementById("characterCount");
const taskList = document.getElementById("taskList");
const taskCount = document.getElementById("taskCount");

const tasksPageList = document.getElementById("tasksPageList");
const allTaskCount = document.getElementById("allTaskCount");
const myTasksList = document.getElementById("myTasksList");
const myTaskCount = document.getElementById("myTaskCount");

const peopleList = document.getElementById("peopleList");
const peopleCount = document.getElementById("peopleCount");
const contactForm = document.getElementById("contactForm");
const contactNameInput = document.getElementById("contactNameInput");
const contactEmailInput = document.getElementById("contactEmailInput");
const contactTypeInput = document.getElementById("contactTypeInput");
const contactSaveMessage = document.getElementById("contactSaveMessage");

const followupList = document.getElementById("followupList");
const followupCount = document.getElementById("followupCount");
const generateFollowupsButton = document.getElementById("generateFollowupsButton");

const taskMeetingForm = document.getElementById("taskMeetingForm");
const taskMeetingTaskInput = document.getElementById("taskMeetingTaskInput");
const taskMeetingTitleInput = document.getElementById("taskMeetingTitleInput");
const taskMeetingLinkInput = document.getElementById("taskMeetingLinkInput");
const taskMeetingTimeInput = document.getElementById("taskMeetingTimeInput");
const taskMeetingSaveMessage = document.getElementById("taskMeetingSaveMessage");
const taskMeetingList = document.getElementById("taskMeetingList");
const taskMeetingCount = document.getElementById("taskMeetingCount");

const activityList = document.getElementById("activityList");
const decisionList = document.getElementById("decisionList");
const decisionCount = document.getElementById("decisionCount");

const riskScore = document.getElementById("riskScore");
const riskBadge = document.getElementById("riskBadge");
const riskDescription = document.getElementById("riskDescription");
const riskSignals = document.getElementById("riskSignals");
const dependencyList = document.getElementById("dependencyList");

const profileMenuButton = document.getElementById("profileMenuButton");
const profileMenu = document.getElementById("profileMenu");
const logoutButton = document.getElementById("logoutButton");
const profileForm = document.getElementById("profileForm");

const taskNotifications = document.getElementById("taskNotifications");
const decisionAlerts = document.getElementById("decisionAlerts");
const automaticFollowups = document.getElementById("automaticFollowups");
const darkMode = document.getElementById("darkMode");
const largeText = document.getElementById("largeText");
const reduceMotion = document.getElementById("reduceMotion");

const navItems = document.querySelectorAll(".nav-item");
const pages = document.querySelectorAll(".app-page");

let dashboardData = {
    tasks: [],
    activities: [],
    dependencies: [],
    decisions: [],
    participants: [],
    people: null,
    followups: [],
    task_meetings: [],
    risk: null,
    user: null
};

if (transcriptInput && characterCount) {
    transcriptInput.addEventListener("input", () => {
        characterCount.textContent = `${transcriptInput.value.length} characters`;
    });
}

if (processButton && transcriptInput) {
    processButton.addEventListener("click", async () => {
        const transcript = transcriptInput.value.trim();

        if (!transcript) {
            alert("Please paste a transcript or update first.");
            return;
        }

        processButton.disabled = true;

        if (processingState) {
            processingState.classList.remove("hidden");
        }

        if (resultsSection) {
            resultsSection.classList.add("hidden");
        }

        try {
            const response = await fetch(`${API_URL}/process-meeting`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    transcript: transcript
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Meeting processing failed.");
            }

            displayMeetingResult(data);

            if (resultsSection) {
                resultsSection.classList.remove("hidden");
            }

            await loadDashboard();
        } catch (error) {
            console.error(error);
            alert(error.message || "Could not connect to MicroManager.");
        } finally {
            if (processingState) {
                processingState.classList.add("hidden");
            }

            processButton.disabled = false;
        }
    });
}

function displayMeetingResult(data) {
    if (!taskList || !taskCount) {
        return;
    }

    const newTasks = data.tasks || [];
    const participants = data.participants || [];

    taskList.innerHTML = "";

    if (participants.length > 0) {
        const participantCard = document.createElement("div");
        participantCard.className = "detected-participants-card";

        participantCard.innerHTML = `
            <div class="detected-participants-heading">
                <strong>People detected</strong>
                <span>${participants.length}</span>
            </div>
            <div class="detected-participants-list">
                ${participants.map((participant) => `
                    <div class="detected-person">
                        <span class="detected-person-avatar">
                            ${escapeHtml(
                                (participant.display_name || participant.detected_name || "?")
                                    .charAt(0)
                                    .toUpperCase()
                            )}
                        </span>
                        <span>
                            <strong>
                                ${escapeHtml(participant.display_name || participant.detected_name || "Unknown")}
                            </strong>
                            <small>
                                ${escapeHtml(participant.match_status || "Detected")}
                            </small>
                        </span>
                    </div>
                `).join("")}
            </div>
        `;

        taskList.appendChild(participantCard);
    }

    if (newTasks.length > 0) {
        taskCount.textContent = newTasks.length;

        newTasks.forEach((task) => {
            taskList.appendChild(createTaskElement(task, "AI detected"));
        });

        return;
    }

    taskCount.textContent = "Updated";

    taskList.insertAdjacentHTML("beforeend", `
        <div class="task">
            <div class="task-left">
                <div class="task-check">Update</div>
                <div>
                    <div class="task-title">Project state updated</div>
                    <div class="task-meta">
                        <span class="meta-pill owner">
                            ${(data.dependencies || []).length} dependencies
                        </span>
                        <span class="meta-pill deadline">
                            ${(data.decisions || []).length} open decisions
                        </span>
                    </div>
                </div>
            </div>
            <div class="task-confidence">
                Risk ${escapeHtml((data.risk && data.risk.level) || "Unknown")}
            </div>
        </div>
    `);
}

async function loadDashboard() {
    try {
        const response = await fetch(`${API_URL}/dashboard`);

        if (!response.ok) {
            throw new Error("Could not load dashboard.");
        }

        dashboardData = await response.json();

        renderTasks(dashboardData.tasks || []);
        renderMyTasks(dashboardData.tasks || []);
        renderFollowups(dashboardData.followups || []);
        renderTaskMeetings(dashboardData.task_meetings || []);
        populateTaskMeetingDropdown(dashboardData.tasks || []);
        renderActivities(dashboardData.activities || []);
        renderDecisions(dashboardData.decisions || []);
        renderRisk(dashboardData.risk);
        renderDependencies(dashboardData.dependencies || []);
        renderUser(dashboardData.user);
        renderPeople(dashboardData.people);

        setText("systemStatus", "All systems operational");
    } catch (error) {
        console.error(error);
        setText("systemStatus", "Backend unavailable");
    }
}

function renderTasks(tasks) {
    if (!tasksPageList || !allTaskCount) {
        return;
    }

    allTaskCount.textContent = tasks.length;
    tasksPageList.innerHTML = "";

    if (tasks.length === 0) {
        tasksPageList.innerHTML = emptyState(
            "None",
            "No tasks yet",
            "Process a meeting to create tasks."
        );
        return;
    }

    tasks.forEach((task) => {
        tasksPageList.appendChild(createTaskElement(task, task.status || "Open"));
    });
}

function renderMyTasks(tasks) {
    if (!myTasksList || !myTaskCount) {
        return;
    }

    const savedName =
        localStorage.getItem("microManagerUserName") ||
        (dashboardData.user && dashboardData.user.name) ||
        "";

    const savedEmail =
        localStorage.getItem("microManagerUserEmail") ||
        (dashboardData.user && dashboardData.user.email) ||
        "";

    const fullName = savedName.toLowerCase().trim();
    const firstName = fullName.split(" ")[0];
    const email = savedEmail.toLowerCase().trim();

    const myTasks = tasks.filter((task) => {
        const owner = (task.owner || "").toLowerCase().trim();

        if (!owner || owner === "unassigned") {
            return false;
        }

        return owner === fullName || owner === firstName || owner === email;
    });

    myTaskCount.textContent = myTasks.length;
    myTasksList.innerHTML = "";

    if (myTasks.length === 0) {
        myTasksList.innerHTML = emptyState(
            "None",
            "No tasks assigned to you yet",
            "When MicroManager detects your name in a meeting, your tasks will appear here."
        );
        return;
    }

    myTasks.forEach((task) => {
        myTasksList.appendChild(createTaskElement(task, task.status || "Open"));
    });
}

function createTaskElement(task, badge) {
    const element = document.createElement("div");
    element.className = "task editable-task";

    const taskName = task.task || "Unknown task";
    const owner = task.owner || "Unassigned";
    const deadline = task.deadline || "";
    const status = task.status || badge || "Open";

    element.innerHTML = `
        <div class="task-left task-main">
            <div class="task-content">
                <div class="task-title">${escapeHtml(taskName)}</div>
                <div class="task-meta">
                    <span class="meta-pill owner">Owner: ${escapeHtml(owner)}</span>
                    <span class="meta-pill deadline">Deadline: ${escapeHtml(formatDeadlineForDisplay(deadline))}</span>
                    <span class="meta-pill status-pill">${escapeHtml(status)}</span>
                </div>
                <div class="task-edit-row hidden">
                    <label>
                        Owner
                        <select class="task-owner-input">
                            ${buildOwnerOptions(owner)}
                        </select>
                    </label>
                    <label>
                        Status
                        <select class="task-status-input">
                            <option value="Open" ${status === "Open" ? "selected" : ""}>Open</option>
                            <option value="In Progress" ${status === "In Progress" ? "selected" : ""}>In Progress</option>
                            <option value="Blocked" ${status === "Blocked" ? "selected" : ""}>Blocked</option>
                            <option value="Done" ${status === "Done" ? "selected" : ""}>Done</option>
                        </select>
                    </label>
                    <label>
                        Deadline
                        <input
                            class="task-deadline-input"
                            type="datetime-local"
                            value="${escapeHtml(formatDeadlineForInput(deadline))}"
                        >
                    </label>
                    <button
                        class="task-save-button"
                        type="button"
                        data-task-id="${task.id}"
                    >
                        Save
                    </button>
                </div>
            </div>
        </div>
        <button class="task-edit-button" type="button">Edit</button>
    `;

    return element;
}

function buildOwnerOptions(currentOwner) {
    const people = dashboardData.people || {};
    const accounts = people.accounts || [];
    const externalGuests = people.external_guests || [];
    const names = ["Unassigned"];

    accounts.forEach((person) => {
        if (person.name && !names.includes(person.name)) {
            names.push(person.name);
        }
    });

    externalGuests.forEach((person) => {
        if (person.name && !names.includes(person.name)) {
            names.push(person.name);
        }
    });

    if (currentOwner && !names.includes(currentOwner)) {
        names.push(currentOwner);
    }

    return names
        .map((name) => `
            <option value="${escapeHtml(name)}" ${name === currentOwner ? "selected" : ""}>
                ${escapeHtml(name)}
            </option>
        `)
        .join("");
}

async function saveTaskChanges(taskId, owner, deadline, status) {
    const response = await fetch(`${API_URL}/tasks/${taskId}`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            owner: owner,
            deadline: deadline,
            status: status
        })
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Could not update task.");
    }

    await loadDashboard();
}

function renderFollowups(followups) {
    if (!followupList || !followupCount) {
        return;
    }

    followupCount.textContent = followups.length;
    followupList.innerHTML = "";

    if (followups.length === 0) {
        followupList.innerHTML = emptyState(
            "None",
            "No follow-ups yet",
            "Process a meeting or generate follow-ups from tasks."
        );
        return;
    }

    followups.forEach((followup) => {
        const element = document.createElement("div");
        element.className = "followup-card";

        element.innerHTML = `
            <div class="followup-top">
                <div>
                    <p class="followup-type">${escapeHtml(followup.followup_type)}</p>
                    <h3>${escapeHtml(followup.title)}</h3>
                </div>
                <span class="followup-status">${escapeHtml(followup.status)}</span>
            </div>
            <p class="followup-message">${escapeHtml(followup.message)}</p>
            <div class="followup-meta">
                <span>Task: ${escapeHtml(followup.task || "Whole project")}</span>
                <span>Owner: ${escapeHtml(followup.owner || "Project team")}</span>
                <span>Deadline: ${escapeHtml(formatDeadlineForDisplay(followup.deadline || ""))}</span>
            </div>
            <div class="followup-actions">
                <button
                    class="followup-action-button"
                    data-followup-id="${followup.id}"
                    data-followup-status="Sent"
                    type="button"
                >
                    Mark sent
                </button>
                <button
                    class="followup-action-button secondary"
                    data-followup-id="${followup.id}"
                    data-followup-status="Dismissed"
                    type="button"
                >
                    Dismiss
                </button>
            </div>
        `;

        followupList.appendChild(element);
    });
}

function populateTaskMeetingDropdown(tasks) {
    if (!taskMeetingTaskInput) {
        return;
    }

    const currentValue = taskMeetingTaskInput.value;

    taskMeetingTaskInput.innerHTML = `
        <option value="">Choose a task or meeting type</option>
        <option value="0">All tasks / project completion discussion</option>
    `;

    tasks.forEach((task) => {
        const option = document.createElement("option");
        option.value = task.id;
        option.textContent = `${task.task} - ${task.owner || "Unassigned"}`;
        taskMeetingTaskInput.appendChild(option);
    });

    taskMeetingTaskInput.value = currentValue;
}

function renderTaskMeetings(taskMeetings) {
    if (!taskMeetingList || !taskMeetingCount) {
        return;
    }

    taskMeetingCount.textContent = taskMeetings.length;
    taskMeetingList.innerHTML = "";

    if (taskMeetings.length === 0) {
        taskMeetingList.innerHTML = emptyState(
            "None",
            "No task meetings yet",
            "Schedule a meeting for work that needs discussion."
        );
        return;
    }

    taskMeetings.forEach((meeting) => {
        const element = document.createElement("div");
        element.className = "task-meeting-card";

        const isProjectMeeting = Number(meeting.task_id) === 0;

        element.innerHTML = `
            <div class="task-meeting-top">
                <div>
                    <p class="task-meeting-label">${escapeHtml(meeting.status || "Scheduled")}</p>
                    <h3>${escapeHtml(meeting.title)}</h3>
                </div>
                <span class="task-meeting-time">
                    ${escapeHtml(formatDeadlineForDisplay(meeting.scheduled_at))}
                </span>
            </div>
            <div class="task-meeting-details">
                <span>Scope: ${isProjectMeeting ? "Whole project" : "Single task"}</span>
                <span>Task: ${escapeHtml(isProjectMeeting ? "All tasks" : meeting.task || "Unknown task")}</span>
                <span>Owner: ${escapeHtml(isProjectMeeting ? "Project team" : meeting.owner || "Unassigned")}</span>
            </div>
            <a
                class="task-meeting-link"
                href="${escapeHtml(meeting.meeting_link)}"
                target="_blank"
                rel="noopener noreferrer"
            >
                Open meeting link
            </a>
        `;

        taskMeetingList.appendChild(element);
    });
}

function renderActivities(activities) {
    if (!activityList) {
        return;
    }

    activityList.innerHTML = "";

    if (activities.length === 0) {
        activityList.innerHTML = emptyState(
            "None",
            "No activity yet",
            "Agent actions will appear here."
        );
        return;
    }

    activities.forEach((activity) => {
        const element = document.createElement("div");
        element.className = "activity-item";

        const successful = activity.activity_type !== "meeting_error";

        element.innerHTML = `
            <div class="activity-dot ${successful ? "success" : ""}"></div>
            <div class="activity-content">
                <strong>${escapeHtml(activity.title)}</strong>
                <p>${escapeHtml(activity.description)}</p>
            </div>
            <span class="activity-time">${formatDate(activity.created_at)}</span>
        `;

        activityList.appendChild(element);
    });
}

function renderDecisions(decisions) {
    if (!decisionList || !decisionCount) {
        return;
    }

    decisionCount.textContent = decisions.length;
    decisionList.innerHTML = "";

    if (decisions.length === 0) {
        decisionList.innerHTML = `
            <div class="dashboard-card empty-state">
                <div class="empty-icon">None</div>
                <h3>No decisions needed</h3>
                <p>MicroManager will only escalate genuine human decisions.</p>
            </div>
        `;
        return;
    }

    decisions.forEach((decision) => {
        const element = document.createElement("div");
        element.className = "dashboard-card";
        element.style.marginBottom = "12px";

        element.innerHTML = `
            <div class="task">
                <div class="task-left">
                    <div class="task-check">Decision</div>
                    <div>
                        <div class="task-title">${escapeHtml(decision.title)}</div>
                        <div class="task-meta">
                            <span class="meta-pill owner">${escapeHtml(decision.priority)} priority</span>
                            <span class="meta-pill deadline">Human decision required</span>
                        </div>
                        <p style="color: #85859a; font-size: 10px; margin-top: 10px;">
                            ${escapeHtml(decision.description)}
                        </p>
                    </div>
                </div>
                <button
                    class="save-button resolve-decision"
                    data-decision-id="${decision.id}"
                    type="button"
                >
                    Resolve
                </button>
            </div>
        `;

        decisionList.appendChild(element);
    });
}

async function resolveDecision(decisionId) {
    try {
        const response = await fetch(`${API_URL}/decisions/${decisionId}/resolve`, {
            method: "PUT"
        });

        if (!response.ok) {
            throw new Error("Could not resolve decision.");
        }

        await loadDashboard();
    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}

function renderRisk(risk) {
    if (!risk || !riskScore || !riskBadge || !riskDescription || !riskSignals) {
        return;
    }

    riskScore.textContent = risk.score;

    const level = risk.level || "Low";

    riskBadge.textContent = `${level.toUpperCase()} RISK`;
    riskBadge.className = `risk-badge ${level.toLowerCase()}`;

    if (level === "Low") {
        riskDescription.textContent = "Project is currently on track.";
    } else if (level === "Medium") {
        riskDescription.textContent = "Some work requires attention.";
    } else {
        riskDescription.textContent = "Project delivery is at risk.";
    }

    riskSignals.innerHTML = "";

    const signals = risk.signals || [];

    if (signals.length === 0) {
        riskSignals.innerHTML = `
            <div class="risk-signal good">
                <div class="risk-signal-title">No major risks detected</div>
                <div class="risk-signal-details">
                    <p>MicroManager did not find blocked, overdue, unassigned, or decision-risk items.</p>
                </div>
            </div>
        `;
        return;
    }

    signals.forEach((signal) => {
        const element = document.createElement("div");
        const isGood = signal === "No major risks detected";
        const details = getRiskSignalDetails(signal);

        element.className = `risk-signal ${isGood ? "good" : ""}`;

        element.innerHTML = `
            <div class="risk-signal-title">${escapeHtml(signal)}</div>
            <div class="risk-signal-details">${details}</div>
        `;

        riskSignals.appendChild(element);
    });
}

function getRiskSignalDetails(signal) {
    const tasks = dashboardData.tasks || [];
    const dependencies = dashboardData.dependencies || [];
    const decisions = dashboardData.decisions || [];
    let matchingItems = [];

    if (signal.includes("blocked task")) {
        matchingItems = tasks
            .filter((task) => (task.status || "").toLowerCase() === "blocked")
            .map((task) => `${task.task} - owner: ${task.owner || "Unassigned"}`);
    }

    if (signal.includes("unassigned task")) {
        matchingItems = tasks
            .filter((task) => {
                const owner = (task.owner || "").trim().toLowerCase();
                return owner === "" || owner === "unassigned";
            })
            .map((task) => `${task.task} - deadline: ${task.deadline || "No deadline"}`);
    }

    if (signal.includes("due soon")) {
        matchingItems = tasks
            .filter((task) => isTaskDueSoon(task))
            .map((task) => `${task.task} - due: ${formatDeadlineForDisplay(task.deadline || "")}`);
    }

    if (signal.includes("overdue")) {
        matchingItems = tasks
            .filter((task) => isTaskOverdue(task))
            .map((task) => `${task.task} - was due: ${formatDeadlineForDisplay(task.deadline || "")}`);
    }

    if (signal.includes("dependency blocker")) {
        matchingItems = dependencies
            .filter((dependency) => {
                const status = (dependency.blocker_status || "").toLowerCase();
                return !["done", "completed", "complete"].includes(status);
            })
            .map((dependency) => `${dependency.task} depends on ${dependency.depends_on_task}`);
    }

    if (signal.includes("human decision")) {
        matchingItems = decisions
            .filter((decision) => {
                const status = (decision.status || "").toLowerCase();
                return status !== "resolved";
            })
            .map((decision) => decision.title);
    }

    if (matchingItems.length === 0) {
        return "<p>No specific item found for this signal.</p>";
    }

    return matchingItems
        .map((item) => `<p>${escapeHtml(item)}</p>`)
        .join("");
}

function renderDependencies(dependencies) {
    if (!dependencyList) {
        return;
    }

    dependencyList.innerHTML = "";

    if (dependencies.length === 0) {
        dependencyList.innerHTML = emptyState(
            "None",
            "No dependencies",
            "No dependency risks detected yet."
        );
        return;
    }

    dependencies.forEach((dependency) => {
        const element = document.createElement("div");
        element.className = "task";
        element.style.marginBottom = "9px";

        element.innerHTML = `
            <div class="task-left">
                <div class="task-check">Dependency</div>
                <div>
                    <div class="task-title">${escapeHtml(dependency.task)}</div>
                    <div class="task-meta">
                        <span class="meta-pill owner">Depends on</span>
                        <span class="meta-pill deadline">
                            ${escapeHtml(dependency.depends_on_task)}
                        </span>
                    </div>
                    <p style="color: #85859a; font-size: 9px; margin-top: 8px;">
                        ${escapeHtml(dependency.description)}
                    </p>
                </div>
            </div>
            <div class="task-confidence">
                Blocker: ${escapeHtml(dependency.blocker_status)}
            </div>
        `;

        dependencyList.appendChild(element);
    });
}

function renderPeople(people) {
    if (!peopleList || !peopleCount) {
        return;
    }

    const accounts = people && people.accounts ? people.accounts : [];
    const guests = people && people.external_guests ? people.external_guests : [];

    const allPeople = [
        ...accounts.map((person) => ({
            ...person,
            label: "Account"
        })),
        ...guests.map((person) => ({
            ...person,
            label: person.contact_type || "External guest"
        }))
    ];

    peopleCount.textContent = allPeople.length;
    peopleList.innerHTML = "";

    if (allPeople.length === 0) {
        peopleList.innerHTML = emptyState(
            "None",
            "No people yet",
            "Process a meeting or add a contact manually."
        );
        return;
    }

    allPeople.forEach((person) => {
        const element = document.createElement("div");
        element.className = "person-card";

        const initial = (person.name || "?").charAt(0).toUpperCase();

        element.innerHTML = `
            <div class="person-avatar">${escapeHtml(initial)}</div>
            <div class="person-details">
                <strong>${escapeHtml(person.name || "Unknown person")}</strong>
                <span>${escapeHtml(person.email || "No email saved")}</span>
            </div>
            <div class="person-type">${escapeHtml(person.label)}</div>
        `;

        peopleList.appendChild(element);
    });
}

function renderUser(user) {
    if (!user) {
        return;
    }

    const savedName = localStorage.getItem("microManagerUserName");
    const savedEmail = localStorage.getItem("microManagerUserEmail");

    const displayUser = {
        ...user,
        name: savedName || user.name || "User",
        email: savedEmail || user.email || "",
        role: user.role || "Team member"
    };

    const workspace =
        localStorage.getItem("microManagerWorkspace") ||
        "MicroManager Demo";

    setInputValue("profileNameInput", displayUser.name);
    setInputValue("profileEmailInput", displayUser.email);
    setInputValue("profileRoleInput", displayUser.role);
    setInputValue("profileWorkspaceInput", workspace);

    updateProfileDisplay(displayUser);
}

function updateProfileDisplay(user) {
    const name = user.name || "User";
    const role = user.role || "Team member";
    const initial = name.trim().charAt(0).toUpperCase() || "U";

    setText("profileName", name);
    setText("profileRole", role);
    setText("profileInitial", initial);
    setText("topAvatarInitial", initial);
    setText("largeProfileInitial", initial);
    setText("profilePageName", name);
    setText("profilePageRole", role);
    setText("greetingName", name.split(" ")[0]);

    updateTopbar(getActivePage());
}

if (profileForm) {
    profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const message = document.getElementById("profileSaveMessage");

        const user = {
            name: getInputValue("profileNameInput").trim(),
            email: getInputValue("profileEmailInput").trim(),
            role: getInputValue("profileRoleInput").trim(),
            workspace: getInputValue("profileWorkspaceInput").trim()
        };

        if (message) {
            message.textContent = "Saving...";
        }

        try {
            const response = await fetch(`${API_URL}/users/me`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    name: user.name,
                    email: user.email,
                    role: user.role
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Could not save profile.");
            }

            localStorage.setItem("microManagerWorkspace", user.workspace);
            localStorage.setItem("microManagerUserName", data.user.name);
            localStorage.setItem("microManagerUserEmail", data.user.email);

            updateProfileDisplay(data.user);
            renderMyTasks(dashboardData.tasks || []);

            if (message) {
                message.style.color = "#39b982";
                message.textContent = "Profile saved";

                window.setTimeout(() => {
                    message.textContent = "";
                }, 2000);
            }

            await loadDashboard();
        } catch (error) {
            if (message) {
                message.style.color = "#c94b5d";
                message.textContent = error.message;
            }
        }
    });
}

if (contactForm) {
    contactForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const name = contactNameInput.value.trim();
        const email = contactEmailInput.value.trim();
        const contactType = contactTypeInput.value.trim() || "External guest";

        if (!name) {
            contactSaveMessage.style.color = "#c94b5d";
            contactSaveMessage.textContent = "Name is required.";
            return;
        }

        contactSaveMessage.style.color = "#85859a";
        contactSaveMessage.textContent = "Saving...";

        try {
            const response = await fetch(`${API_URL}/contacts`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    name: name,
                    email: email,
                    contact_type: contactType
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Could not add contact.");
            }

            contactForm.reset();
            contactTypeInput.value = "External guest";
            contactSaveMessage.style.color = "#39b982";
            contactSaveMessage.textContent = "Contact added";

            renderPeople(data.people);

            window.setTimeout(() => {
                contactSaveMessage.textContent = "";
            }, 2000);

            await loadDashboard();
        } catch (error) {
            contactSaveMessage.style.color = "#c94b5d";
            contactSaveMessage.textContent = error.message;
        }
    });
}

if (taskMeetingForm) {
    taskMeetingForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const taskId = Number(taskMeetingTaskInput.value);
        const title = taskMeetingTitleInput.value.trim();
        const meetingLink = taskMeetingLinkInput.value.trim();
        const scheduledAt = taskMeetingTimeInput.value;

        if (taskMeetingTaskInput.value === "" || !title || !meetingLink || !scheduledAt) {
            taskMeetingSaveMessage.style.color = "#c94b5d";
            taskMeetingSaveMessage.textContent = "Fill all meeting fields.";
            return;
        }

        taskMeetingSaveMessage.style.color = "#85859a";
        taskMeetingSaveMessage.textContent = "Scheduling...";

        try {
            const response = await fetch(`${API_URL}/task-meetings`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    task_id: taskId,
                    title: title,
                    meeting_link: meetingLink,
                    scheduled_at: scheduledAt
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Could not schedule meeting.");
            }

            taskMeetingForm.reset();
            taskMeetingSaveMessage.style.color = "#39b982";
            taskMeetingSaveMessage.textContent = "Meeting scheduled";

            await loadDashboard();

            window.setTimeout(() => {
                taskMeetingSaveMessage.textContent = "";
            }, 2000);
        } catch (error) {
            taskMeetingSaveMessage.style.color = "#c94b5d";
            taskMeetingSaveMessage.textContent = error.message;
        }
    });
}

if (profileMenuButton && profileMenu) {
    profileMenuButton.addEventListener("click", (event) => {
        event.stopPropagation();

        const opening = profileMenu.classList.contains("hidden");

        profileMenu.classList.toggle("hidden", !opening);
        profileMenuButton.setAttribute("aria-expanded", String(opening));
    });

    profileMenu.addEventListener("click", (event) => {
        const button = event.target.closest("[data-profile-page]");

        if (button) {
            showPage(button.dataset.profilePage);
        }
    });

    document.addEventListener("click", (event) => {
        if (
            !profileMenu.contains(event.target) &&
            !profileMenuButton.contains(event.target)
        ) {
            closeProfileMenu();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeProfileMenu();
        }
    });
}

function closeProfileMenu() {
    if (!profileMenu || !profileMenuButton) {
        return;
    }

    profileMenu.classList.add("hidden");
    profileMenuButton.setAttribute("aria-expanded", "false");
}

if (logoutButton) {
    logoutButton.addEventListener("click", () => {
        closeProfileMenu();

        localStorage.removeItem("microManagerLoggedIn");
        localStorage.removeItem("microManagerUserName");
        localStorage.removeItem("microManagerUserEmail");
        localStorage.removeItem("microManagerWorkspace");

        window.location.href = "login.html";
    });
}

navItems.forEach((item) => {
    item.addEventListener("click", () => {
        showPage(item.dataset.page);
    });
});

function showPage(target) {
    const selectedPage = document.getElementById(`page-${target}`);

    if (!selectedPage) {
        return;
    }

    navItems.forEach((item) => {
        item.classList.toggle("active", item.dataset.page === target);
    });

    pages.forEach((page) => {
        page.classList.add("hidden");
    });

    selectedPage.classList.remove("hidden");

    closeProfileMenu();
    updateTopbar(target);
    loadDashboard();
}

function getActivePage() {
    const activeItem = document.querySelector(".nav-item.active");

    if (!activeItem) {
        return "meeting";
    }

    return activeItem.dataset.page || "meeting";
}

document.addEventListener("click", async (event) => {
    const button = event.target.closest(".task-save-button");

    if (!button) {
        return;
    }

    const taskCard = button.closest(".task");
    const owner = taskCard.querySelector(".task-owner-input").value;
    const status = taskCard.querySelector(".task-status-input").value;
    const deadline = taskCard.querySelector(".task-deadline-input").value;

    button.disabled = true;
    button.textContent = "Saving...";

    try {
        await saveTaskChanges(
            button.dataset.taskId,
            owner,
            deadline,
            status
        );
    } catch (error) {
        console.error(error);
        alert(error.message || "Could not save task.");

        button.disabled = false;
        button.textContent = "Save";
    }
});

document.addEventListener("click", (event) => {
    const editButton = event.target.closest(".task-edit-button");

    if (!editButton) {
        return;
    }

    const taskCard = editButton.closest(".task");
    const editRow = taskCard.querySelector(".task-edit-row");

    editRow.classList.toggle("hidden");

    editButton.textContent = editRow.classList.contains("hidden")
        ? "Edit"
        : "Cancel";
});

document.addEventListener("click", async (event) => {
    const button = event.target.closest(".resolve-decision");

    if (!button) {
        return;
    }

    await resolveDecision(button.dataset.decisionId);
});

if (generateFollowupsButton) {
    generateFollowupsButton.addEventListener("click", async () => {
        generateFollowupsButton.disabled = true;
        generateFollowupsButton.textContent = "Generating...";

        try {
            const response = await fetch(`${API_URL}/followups/generate`, {
                method: "POST"
            });

            if (!response.ok) {
                throw new Error("Could not generate follow-ups.");
            }

            await loadDashboard();
        } catch (error) {
            console.error(error);
            alert(error.message);
        } finally {
            generateFollowupsButton.disabled = false;
            generateFollowupsButton.textContent = "Generate follow-ups";
        }
    });
}

document.addEventListener("click", async (event) => {
    const button = event.target.closest(".followup-action-button");

    if (!button) {
        return;
    }

    const followupId = button.dataset.followupId;
    const status = button.dataset.followupStatus;

    button.disabled = true;
    button.textContent = "Updating...";

    try {
        const response = await fetch(
            `${API_URL}/followups/${followupId}/status?status=${encodeURIComponent(status)}`,
            {
                method: "PUT"
            }
        );

        if (!response.ok) {
            throw new Error("Could not update follow-up.");
        }

        await loadDashboard();
    } catch (error) {
        console.error(error);
        alert(error.message);
    }
});

function loadSettings() {
    let settings = {};

    try {
        settings = JSON.parse(localStorage.getItem("microManagerSettings")) || {};
    } catch {
        settings = {};
    }

    if (taskNotifications) {
        taskNotifications.checked = settings.taskNotifications ?? true;
    }

    if (decisionAlerts) {
        decisionAlerts.checked = settings.decisionAlerts ?? true;
    }

    if (automaticFollowups) {
        automaticFollowups.checked = settings.automaticFollowups ?? false;
    }

    if (darkMode) {
        darkMode.checked = settings.darkMode ?? false;
    }

    if (largeText) {
        largeText.checked = settings.largeText ?? false;
    }

    if (reduceMotion) {
        reduceMotion.checked = settings.reduceMotion ?? false;
    }

    applyAccessibilitySettings(settings);
}

function saveSettings() {
    const settings = {
        taskNotifications: taskNotifications ? taskNotifications.checked : true,
        decisionAlerts: decisionAlerts ? decisionAlerts.checked : true,
        automaticFollowups: automaticFollowups ? automaticFollowups.checked : false,
        darkMode: darkMode ? darkMode.checked : false,
        largeText: largeText ? largeText.checked : false,
        reduceMotion: reduceMotion ? reduceMotion.checked : false
    };

    localStorage.setItem("microManagerSettings", JSON.stringify(settings));

    applyAccessibilitySettings(settings);
}

function applyAccessibilitySettings(settings) {
    document.body.classList.toggle("dark-mode", settings.darkMode === true);
    document.body.classList.toggle("large-text", settings.largeText === true);
    document.body.classList.toggle("reduce-motion", settings.reduceMotion === true);
}

[
    taskNotifications,
    decisionAlerts,
    automaticFollowups,
    darkMode,
    largeText,
    reduceMotion
].forEach((setting) => {
    if (setting) {
        setting.addEventListener("change", saveSettings);
    }
});

function updateTopbar(page) {
    const information = {
        meeting: [
            "WORKSPACE / MEETING",
            `Good evening, ${getGreetingName()}`,
            "Turn conversations into actions."
        ],
        tasks: [
            "WORKSPACE / TASKS",
            "Execution board",
            "Track all work extracted from your meetings."
        ],
        mytasks: [
            "WORKSPACE / MY TASKS",
            "My tasks",
            "Work automatically assigned to you from meetings."
        ],
        people: [
            "WORKSPACE / PEOPLE",
            "People and contacts",
            "Manage teammates, detected participants and external collaborators."
        ],
        followups: [
            "WORKSPACE / FOLLOW-UPS",
            "Follow-ups",
            "Generated reminders and next actions."
        ],
        meetings: [
            "WORKSPACE / TASK MEETINGS",
            "Task meeting scheduler",
            "Schedule follow-up meetings for work that needs discussion."
        ],
        activity: [
            "WORKSPACE / AGENT ACTIVITY",
            "Agent activity",
            "See what MicroManager is doing automatically."
        ],
        decisions: [
            "WORKSPACE / DECISION INBOX",
            "Decision inbox",
            "Human decisions only when necessary."
        ],
        risk: [
            "WORKSPACE / PROJECT RISK",
            "Project intelligence",
            "Understand blockers before they become problems."
        ],
        user: [
            "WORKSPACE / PROFILE",
            "Your profile",
            "Manage your MicroManager account."
        ],
        settings: [
            "WORKSPACE / SETTINGS",
            "Settings",
            "Control notifications and agent behaviour."
        ]
    };

    const selected = information[page];

    if (!selected) {
        return;
    }

    setText("topbarEyebrow", selected[0]);

    const title = document.getElementById("topbarTitle");

    if (title) {
        title.textContent = selected[1];
    }

    setText("topbarSubtitle", selected[2]);
}

function getGreetingName() {
    const savedName = localStorage.getItem("microManagerUserName");

    if (savedName) {
        return savedName.split(" ")[0];
    }

    if (dashboardData.user && dashboardData.user.name) {
        return dashboardData.user.name.split(" ")[0];
    }

    return "User";
}

function formatDeadlineForInput(deadline) {
    if (!deadline) {
        return "";
    }

    if (deadline.includes("T")) {
        return deadline.slice(0, 16);
    }

    const date = new Date(deadline);

    if (Number.isNaN(date.getTime())) {
        return "";
    }

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hour = String(date.getHours()).padStart(2, "0");
    const minute = String(date.getMinutes()).padStart(2, "0");

    return `${year}-${month}-${day}T${hour}:${minute}`;
}

function formatDeadlineForDisplay(deadline) {
    if (!deadline) {
        return "No deadline";
    }

    const date = new Date(deadline);

    if (Number.isNaN(date.getTime())) {
        return deadline;
    }

    return date.toLocaleString([], {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function isTaskDueSoon(task) {
    const deadline = task.deadline || "";
    const status = (task.status || "").toLowerCase();

    if (!deadline.includes("T") || status === "done") {
        return false;
    }

    const deadlineDate = new Date(deadline);
    const now = new Date();

    if (Number.isNaN(deadlineDate.getTime())) {
        return false;
    }

    const difference = deadlineDate.getTime() - now.getTime();
    const days = difference / (1000 * 60 * 60 * 24);

    return days >= 0 && days <= 2;
}

function isTaskOverdue(task) {
    const deadline = task.deadline || "";
    const status = (task.status || "").toLowerCase();

    if (!deadline.includes("T") || status === "done") {
        return false;
    }

    const deadlineDate = new Date(deadline);
    const now = new Date();

    if (Number.isNaN(deadlineDate.getTime())) {
        return false;
    }

    return deadlineDate < now;
}

function emptyState(label, title, description) {
    return `
        <div class="empty-state">
            <div class="empty-icon">${escapeHtml(label)}</div>
            <h3>${escapeHtml(title)}</h3>
            <p>${escapeHtml(description)}</p>
        </div>
    `;
}

function formatDate(value) {
    if (!value) {
        return "";
    }

    const date = new Date(value.replace(" ", "T") + "Z");

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value;
    }
}

function setInputValue(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.value = value || "";
    }
}

function getInputValue(id) {
    const element = document.getElementById(id);

    if (!element) {
        return "";
    }

    return element.value || "";
}

loadSettings();
loadDashboard();