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
    if (member.admin) {
        const badge = document.createElement("span");
        badge.className = "admin-badge";
        badge.textContent = "Instructor";
        nameCell.append(document.createTextNode(" "), badge);
    }
    const emailCell = document.createElement("td");
    emailCell.textContent = member.email || "";
    const beltCell = document.createElement("td");
    const select = beltSelect(member.rank);
    beltCell.append(select);
    const actionCell = document.createElement("td");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "login-button admin-save";
    button.textContent = "Save";
    button.addEventListener("click", function () {
        saveRank(member.id, nameInput.value, select.value, button);
    });
    actionCell.append(button);
    row.append(nameCell, emailCell, beltCell, actionCell);
    tableBody.append(row);
}

async function saveRank(id, name, rank, button) {
    button.disabled = true;
    try {
        const response = await fetch("/api/admin/rank", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: id, name: name, rank: rank })
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

if (tableBody) {
    loadMembers();
}
