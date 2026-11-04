// Member greeting and menu locks. The server decides which pages are sent.
// Rank numbers here match server.py and only affect labels and locked links.

const RANKS = {
    white: { level: 1, label: "White Belt" },
    "10th": { level: 2, label: "10th Gold" },
    "9th": { level: 3, label: "9th Purple" },
    "8th": { level: 4, label: "8th Orange" },
    "7th": { level: 5, label: "7th Blue" },
    "6th": { level: 6, label: "6th Green" },
    "5th": { level: 7, label: "5th Green" },
    "4th": { level: 8, label: "4th Brown" },
    "3rd": { level: 9, label: "3rd Brown" },
    "2nd": { level: 10, label: "2nd Red" },
    "1st": { level: 11, label: "1st Red" },
    black: { level: 12, label: "Black Belt" }
};

const PAGE_LEVEL = {
    "white-belts.html": 1,
    "10th-gold.html": 2,
    "9th-purple.html": 3,
    "8th-orange.html": 4,
    "7th-blue.html": 5,
    "6th-green.html": 6,
    "5th-green.html": 7,
    "4th-brown.html": 8,
    "3rd-brown.html": 9,
    "2nd-red.html": 10,
    "1st-red.html": 11,
    "giecho-il-bu.html": 2,
    "giecho-yi-bu.html": 3,
    "giecho-sahm-bu.html": 4,
    "pyong-an-cho-dan.html": 5,
    "pyong-an-yi-dan.html": 6,
    "pyong-an-sahm-dan.html": 7,
    "pyong-an-sa-dan.html": 8,
    "nahanchi-sahm-dan.html": 9,
    "pyong-an-oh-dan.html": 10,
    "empi.html": 11,
    "bassai.html": 12,
    "one-steps.html": 1
};

let currentSession = null;

function rankLevel(rankId) {
    return Object.prototype.hasOwnProperty.call(RANKS, rankId) ? RANKS[rankId].level : 0;
}

function rankLabel(rankId) {
    return Object.prototype.hasOwnProperty.call(RANKS, rankId) ? RANKS[rankId].label : "Guest";
}

function rankIdForLevel(level) {
    const ids = Object.keys(RANKS);
    for (let i = 0; i < ids.length; i++) {
        if (RANKS[ids[i]].level === level) {
            return ids[i];
        }
    }
    return "black";
}

function requiredLevelForFile(file) {
    if (Object.prototype.hasOwnProperty.call(PAGE_LEVEL, file)) {
        return PAGE_LEVEL[file];
    }
    return 0;
}

function siteRelativePath() {
    let path = "";
    try {
        path = decodeURIComponent(location.pathname);
    } catch (error) {
        path = location.pathname;
    }
    path = path.replace(/\\/g, "/").replace(/^\/+/, "");
    if (!path || path.endsWith("/")) {
        path += "index.html";
    }
    return path;
}

function loginHref() {
    const relative = siteRelativePath();
    const depth = relative.split("/").length - 1;
    return "../".repeat(depth) + "login.html?next=" + encodeURIComponent(relative);
}

function fileFromHref(href) {
    if (!href || href.startsWith("#") || href.startsWith("mailto:")) {
        return "";
    }
    const clean = href.split("?")[0].split("#")[0];
    const file = clean.split("/").pop();
    return file || "";
}

function readCookie(name) {
    const prefix = name + "=";
    const parts = document.cookie ? document.cookie.split("; ") : [];
    for (let i = 0; i < parts.length; i++) {
        if (parts[i].indexOf(prefix) === 0) {
            try {
                return decodeURIComponent(parts[i].slice(prefix.length));
            } catch (error) {
                return "";
            }
        }
    }
    return "";
}

function sessionFromToken(token) {
    const parts = typeof token === "string" ? token.split(".") : [];
    if (parts.length !== 3 || !parts[1]) {
        return null;
    }
    try {
        const padded = parts[1].replace(/-/g, "+").replace(/_/g, "/") + "===".slice((parts[1].length + 3) % 4);
        const data = JSON.parse(atob(padded));
        if (!data || typeof data.name !== "string" || typeof data.exp !== "number" || data.exp * 1000 <= Date.now()) {
            return null;
        }
        return {
            displayName: data.name,
            rank: typeof data.rank === "string" ? data.rank : null,
            admin: data.admin === true,
            iat: typeof data.iat === "number" ? data.iat : 0
        };
    } catch (error) {
        return null;
    }
}

function readSession() {
    return sessionFromToken(readCookie("ckaf_session"));
}

async function refreshSession() {
    try {
        const response = await fetch("/api/me", { credentials: "same-origin" });
        if (!response.ok) {
            return null;
        }
        const data = await response.json();
        if (!data || typeof data.displayName !== "string") {
            return null;
        }
        return {
            displayName: data.displayName,
            rank: typeof data.rank === "string" ? data.rank : null,
            admin: data.isAdmin === true,
            iat: Math.floor(Date.now() / 1000)
        };
    } catch (error) {
        return null;
    }
}

async function logout() {
    await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
}

function showGate(requiredLevel) {
    const content = document.querySelector(".content");
    if (!content || content.querySelector(".access-gate")) {
        return;
    }
    const required = rankLabel(rankIdForLevel(requiredLevel));
    const panel = document.createElement("div");
    panel.className = "access-gate";

    const heading = document.createElement("h2");
    heading.textContent = "Members only";

    const message = document.createElement("p");
    if (currentSession && currentSession.rank) {
        message.textContent = "This page is for " + required + " and above. You are signed in as " + rankLabel(currentSession.rank) + ".";
    } else if (currentSession) {
        message.textContent = "This page is for members with a rank on file. Ask an instructor to set your rank.";
    } else {
        message.textContent = "This page is for " + required + " and above. Sign in to continue.";
    }

    const link = document.createElement("a");
    link.className = "gate-link";
    link.href = loginHref();
    link.textContent = currentSession ? "Switch account" : "Sign in";

    panel.append(heading, message, link);
    content.replaceChildren(panel);
}

function gateSections() {
    const level = currentSession && currentSession.rank ? rankLevel(currentSession.rank) : 0;
    document.querySelectorAll("[data-min-rank]").forEach(function (section) {
        const rank = section.getAttribute("data-min-rank");
        if (level >= rankLevel(rank)) {
            return;
        }
        const heading = section.previousElementSibling;
        if (heading && heading.classList.contains("section-heading")) {
            heading.remove();
        }
        const note = document.createElement("p");
        note.className = "rank-note";
        const name = section.getAttribute("data-section-name") || "This section";
        note.textContent = name + " is available to " + rankLabel(rank) + " and above.";
        section.replaceWith(note);
    });
}

function renderGreeting() {
    const greeting = document.getElementById("greeting");
    if (!greeting) {
        return;
    }
    greeting.replaceChildren();
    if (!currentSession) {
        return;
    }
    const label = currentSession.rank ? " (" + rankLabel(currentSession.rank) + ")" : "";
    greeting.append(document.createTextNode("Hello, " + currentSession.displayName + label + "! "));
    const button = document.createElement("button");
    button.type = "button";
    button.className = "logout-button";
    button.textContent = "Log out";
    button.addEventListener("click", function () {
        logout().finally(function () {
            window.location.reload();
        });
    });
    greeting.append(button);
}

function ensureGreeting() {
    if (document.getElementById("greeting")) {
        return;
    }
    const header = document.querySelector("header");
    if (!header) {
        return;
    }
    const greeting = document.createElement("div");
    greeting.id = "greeting";
    greeting.className = "greeting";
    header.insertBefore(greeting, header.firstChild);
}

function accountPrefix(loginAnchor) {
    const href = (loginAnchor.getAttribute("href") || "login.html").split("?")[0];
    const at = href.lastIndexOf("login.html");
    return at >= 0 ? href.slice(0, at) : "";
}

function ensureAccountLinks() {
    document.querySelectorAll(".menu-line").forEach(function (line) {
        const login = Array.prototype.find.call(line.querySelectorAll("a"), function (anchor) {
            return fileFromHref(anchor.getAttribute("href")) === "login.html";
        });
        if (!login) {
            return;
        }
        const prefix = accountPrefix(login);
        if (!line.querySelector("a[href$='register.html']")) {
            const register = document.createElement("a");
            register.href = prefix + "register.html";
            register.textContent = "Register";
            login.before(register, document.createTextNode(" "));
        }
        if (currentSession && !line.querySelector("a[href$='account.html']")) {
            const account = document.createElement("a");
            account.href = prefix + "account.html";
            account.textContent = "Account";
            login.before(account, document.createTextNode(" "));
        }
        if (currentSession && currentSession.admin && !line.querySelector("a[href$='admin.html']")) {
            const admin = document.createElement("a");
            admin.href = prefix + "admin.html";
            admin.textContent = "Admin";
            login.before(admin, document.createTextNode(" "));
        }
    });
}

function updateMenu() {
    ensureAccountLinks();
    const level = currentSession && currentSession.rank ? rankLevel(currentSession.rank) : 0;
    document.querySelectorAll("a[href]").forEach(function (anchor) {
        const href = anchor.getAttribute("href");
        const file = fileFromHref(href);
        if (file === "login.html") {
            if (!currentSession || anchor.classList.contains("gate-link")) {
                return;
            }
            anchor.textContent = "Log out";
            anchor.addEventListener("click", function (event) {
                event.preventDefault();
                logout().finally(function () {
                    window.location.reload();
                });
            });
            return;
        }
        const need = requiredLevelForFile(file);
        if (need > level) {
            anchor.classList.add("rank-locked");
            anchor.title = "Requires " + rankLabel(rankIdForLevel(need)) + " or above";
        }
    });
}

function protectPage() {
    const required = requiredLevelForFile(fileFromHref(siteRelativePath()));
    const level = currentSession && currentSession.rank ? rankLevel(currentSession.rank) : 0;
    if (required > level) {
        showGate(required);
        return;
    }
    gateSections();
}

function sameMember(left, right) {
    if (!left || !right) {
        return false;
    }
    return left.displayName === right.displayName && left.rank === right.rank && left.admin === right.admin;
}

function initPage() {
    currentSession = readSession();
    ensureGreeting();
    renderGreeting();
    updateMenu();
    protectPage();
    const age = currentSession ? Math.floor(Date.now() / 1000) - currentSession.iat : 0;
    if (!currentSession || age < 300) {
        return;
    }
    refreshSession().then(function (fresh) {
        if (!fresh || sameMember(currentSession, fresh)) {
            return;
        }
        currentSession = fresh;
        renderGreeting();
        updateMenu();
    });
}

function onReady(callback) {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", callback);
    } else {
        callback();
    }
}

if (typeof document !== "undefined") {
    window.ckafReadSession = readSession;
    onReady(initPage);
}
