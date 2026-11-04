const BELTS = [
    ["white", "White Belt"],
    ["10th", "10th Gold"],
    ["9th", "9th Purple"],
    ["8th", "8th Orange"],
    ["7th", "7th Blue"],
    ["6th", "6th Green"],
    ["5th", "5th Green"],
    ["4th", "4th Brown"],
    ["3rd", "3rd Brown"],
    ["2nd", "2nd Red"],
    ["1st", "1st Red"],
    ["black", "Black Belt"]
];

const messageEl = document.getElementById("admin-message");
const tableBody = document.querySelector("#member-table tbody");

function showAdminMessage(message, ok) {
    if (!messageEl) {
        return;
    }
    messageEl.textContent = message;
    messageEl.classList.toggle("success", Boolean(ok));
    messageEl.classList.add("visible");
}

function beltSelect(selected) {
    const select = document.createElement("select");
    BELTS.forEach(function (belt) {
        const option = document.createElement("option");
        option.value = belt[0];
        option.textContent = belt[1];
        if (belt[0] === selected) {
            option.selected = true;
        }
        select.append(option);
    });
    return select;
}

function addMemberRow(member) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.maxLength = 80;
    nameInput.value = member.displayName || "";
    nameInput.setAttribute("aria-label", "Name");
    nameCell.append(nameInput);
    const emailCell = document.createElement("td");
    emailCell.textContent = member.email || "";
    const beltCell = document.createElement("td");
    const select = beltSelect(member.rank);
    beltCell.append(select);
    const instructorCell = document.createElement("td");
    const instructor = document.createElement("input");
    instructor.type = "checkbox";
    instructor.checked = member.admin === true;
    instructor.setAttribute("aria-label", "Instructor for " + (member.displayName || member.email || "member"));
    instructorCell.append(instructor);
    const actionCell = document.createElement("td");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "login-button admin-save";
    button.textContent = "Save";
    button.addEventListener("click", function () {
        saveRank(member.id, nameInput.value, select.value, instructor.checked, button);
    });
    actionCell.append(button);
    row.append(nameCell, emailCell, beltCell, instructorCell, actionCell);
    tableBody.append(row);
}

async function saveRank(id, name, rank, instructor, button) {
    button.disabled = true;
    try {
        const response = await fetch("/api/admin/rank", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: id, name: name, rank: rank, admin: instructor })
        });
        let result = {};
        try {
            result = await response.json();
        } catch (error) {
            result = {};
        }
        if (!response.ok) {
            showAdminMessage(result.message || "That belt was not saved.");
            button.disabled = false;
            return;
        }
        showAdminMessage("Saved " + (result.displayName || name) + ".", true);
    } catch (error) {
        showAdminMessage("The member list is unavailable. Reload the page and try again.");
    }
    button.disabled = false;
}

async function loadMembers() {
    if (!tableBody) {
        return;
    }
    try {
        const response = await fetch("/api/admin/members", { credentials: "same-origin" });
        let result = {};
        try {
            result = await response.json();
        } catch (error) {
            result = {};
        }
        if (!response.ok) {
            showAdminMessage(result.message || "The member list is unavailable.");
            return;
        }
        tableBody.replaceChildren();
        const members = Array.isArray(result.members) ? result.members : [];
        if (!members.length) {
            showAdminMessage("No members have registered yet.");
            return;
        }
        members.forEach(addMemberRow);
    } catch (error) {
        showAdminMessage("The member list is unavailable. Reload the page and try again.");
    }
}

function formatWhen(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    return date.toLocaleString();
}

function addSuggestion(note) {
    const list = document.getElementById("suggestion-list");
    const card = document.createElement("article");
    card.className = "suggestion-card";
    const heading = document.createElement("h3");
    const when = formatWhen(note.createdAt);
    heading.textContent = when ? (note.name || "A visitor") + " · " + when : (note.name || "A visitor");
    const body = document.createElement("p");
    body.textContent = note.message || "";
    card.append(heading, body);
    list.append(card);
}

async function loadSuggestions() {
    const list = document.getElementById("suggestion-list");
    if (!list) {
        return;
    }
    try {
        const response = await fetch("/api/admin/suggestions", { credentials: "same-origin" });
        let result = {};
        try {
            result = await response.json();
        } catch (error) {
            result = {};
        }
        list.replaceChildren();
        if (!response.ok) {
            const notice = document.createElement("p");
            notice.textContent = result.message || "Suggestions are unavailable right now.";
            list.append(notice);
            return;
        }
        const notes = Array.isArray(result.suggestions) ? result.suggestions : [];
        if (!notes.length) {
            const notice = document.createElement("p");
            notice.textContent = "No suggestions yet.";
            list.append(notice);
            return;
        }
        notes.forEach(addSuggestion);
    } catch (error) {
        list.replaceChildren();
        const notice = document.createElement("p");
        notice.textContent = "Suggestions are unavailable right now.";
        list.append(notice);
    }
}

if (tableBody) {
    loadMembers();
    loadSuggestions();
}
