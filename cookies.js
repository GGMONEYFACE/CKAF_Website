// Signed session cookie for the class demo.
// A visitor cannot raise their belt by editing the cookie. The check runs
// in the browser, which matches this project. A public site would check
// the password on a server so the account list is not in the page.

const SESSION_SECRET = "ckaf-3000-session-9f3c2a7e1b84d6c0";
const SESSION_COOKIE = "ckaf_session";
const ATTEMPT_KEY = "ckaf_attempts";
const RETURN_KEY = "ckaf_return";
const MAX_ATTEMPTS = 5;
const LOCKOUT_MS = 30000;
const SESSION_SECONDS = 60 * 60 * 12;
const REMEMBER_SECONDS = 60 * 60 * 24 * 7;

const RANKS = {
    guest: { level: 0, label: "Guest" },
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

// Forms and testing pages are visible at the belt that requires them, and above.
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
    "bassai.html": 12
};

const ACCOUNTS = [
    {
        username: "white",
        displayName: "Casey",
        rank: "white",
        passwordHash: "ecab3843d0a512ceac63dfcc41a526348af47aaebc455f18191fdf1af1e2b536"
    },
    {
        username: "gideon",
        displayName: "Gideon",
        rank: "5th",
        passwordHash: "b8284eafb05adb1576b3e837166ef7f6671ced24835195a8f91d736110be5b65"
    },
    {
        username: "david",
        displayName: "David",
        rank: "1st",
        passwordHash: "3524fe5ae10d268ace21fd97d7121a20f3fcf6350bd32e0f1cb340c4375151b6"
    },
    {
        username: "instructor",
        displayName: "Coach",
        rank: "black",
        passwordHash: "b8e6a180a221187e9c43e4a2499d439f4ebe267ef44b5f7e83d747e747ac70cf"
    }
];

const SHA256_K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
];

function rotr(value, bits) {
    return ((value >>> bits) | (value << (32 - bits))) >>> 0;
}

function sha256(message) {
    const bytes = [];
    for (let i = 0; i < message.length; i++) {
        const code = message.charCodeAt(i);
        if (code > 255) {
            return null;
        }
        bytes.push(code);
    }

    const bitLength = bytes.length * 8;
    bytes.push(0x80);
    while (bytes.length % 64 !== 56) {
        bytes.push(0);
    }

    const high = Math.floor(bitLength / 0x100000000);
    const low = bitLength >>> 0;
    bytes.push((high >>> 24) & 0xff, (high >>> 16) & 0xff, (high >>> 8) & 0xff, high & 0xff);
    bytes.push((low >>> 24) & 0xff, (low >>> 16) & 0xff, (low >>> 8) & 0xff, low & 0xff);

    const hash = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ];

    for (let offset = 0; offset < bytes.length; offset += 64) {
        const schedule = new Array(64);
        for (let i = 0; i < 16; i++) {
            const index = offset + i * 4;
            schedule[i] = (
                (bytes[index] << 24) |
                (bytes[index + 1] << 16) |
                (bytes[index + 2] << 8) |
                bytes[index + 3]
            ) >>> 0;
        }
        for (let i = 16; i < 64; i++) {
            const s0 = rotr(schedule[i - 15], 7) ^ rotr(schedule[i - 15], 18) ^ (schedule[i - 15] >>> 3);
            const s1 = rotr(schedule[i - 2], 17) ^ rotr(schedule[i - 2], 19) ^ (schedule[i - 2] >>> 10);
            schedule[i] = (schedule[i - 16] + s0 + schedule[i - 7] + s1) >>> 0;
        }

        let a = hash[0];
        let b = hash[1];
        let c = hash[2];
        let d = hash[3];
        let e = hash[4];
        let f = hash[5];
        let g = hash[6];
        let h = hash[7];

        for (let i = 0; i < 64; i++) {
            const sigma1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            const choose = ((e & f) ^ (~e & g)) >>> 0;
            const temp1 = (h + sigma1 + choose + SHA256_K[i] + schedule[i]) >>> 0;
            const sigma0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            const majority = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
            const temp2 = (sigma0 + majority) >>> 0;
            h = g;
            g = f;
            f = e;
            e = (d + temp1) >>> 0;
            d = c;
            c = b;
            b = a;
            a = (temp1 + temp2) >>> 0;
        }

        hash[0] = (hash[0] + a) >>> 0;
        hash[1] = (hash[1] + b) >>> 0;
        hash[2] = (hash[2] + c) >>> 0;
        hash[3] = (hash[3] + d) >>> 0;
        hash[4] = (hash[4] + e) >>> 0;
        hash[5] = (hash[5] + f) >>> 0;
        hash[6] = (hash[6] + g) >>> 0;
        hash[7] = (hash[7] + h) >>> 0;
    }

    return hash.map(function (value) {
        return value.toString(16).padStart(8, "0");
    }).join("");
}

if (sha256("abc") !== "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") {
    throw new Error("SHA-256 self-check failed");
}

function hashesMatch(left, right) {
    if (typeof left !== "string" || typeof right !== "string" || left.length !== right.length) {
        return false;
    }
    let difference = 0;
    for (let i = 0; i < left.length; i++) {
        difference |= left.charCodeAt(i) ^ right.charCodeAt(i);
    }
    return difference === 0;
}

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
    if (file === "one-steps.html") {
        return 1;
    }
    if (Object.prototype.hasOwnProperty.call(PAGE_LEVEL, file)) {
        return PAGE_LEVEL[file];
    }
    return 0;
}

function getCookie(name) {
    const nameEQ = name + "=";
    const cookies = document.cookie.split(";");
    for (let cookie of cookies) {
        cookie = cookie.trim();
        if (cookie.indexOf(nameEQ) === 0) {
            return decodeURIComponent(cookie.substring(nameEQ.length));
        }
    }
    return null;
}

function writeCookie(name, value, maxAgeSeconds) {
    const parts = [name + "=" + encodeURIComponent(value), "path=/", "SameSite=Lax"];
    if (location.protocol === "https:") {
        parts.push("Secure");
    }
    if (typeof maxAgeSeconds === "number") {
        parts.push("max-age=" + String(maxAgeSeconds));
    }
    document.cookie = parts.join("; ");
}

function deleteCookie(name) {
    document.cookie = name + "=; path=/; max-age=0; SameSite=Lax";
}

function readAttempts() {
    try {
        const parsed = JSON.parse(sessionStorage.getItem(ATTEMPT_KEY) || "");
        if (parsed && typeof parsed.count === "number" && typeof parsed.until === "number") {
            return parsed;
        }
    } catch (error) {
        // Ignore a damaged attempt counter and start over.
    }
    return { count: 0, until: 0 };
}

function recordFailure() {
    const state = readAttempts();
    if (state.until > Date.now()) {
        return state;
    }
    state.count += 1;
    if (state.count >= MAX_ATTEMPTS) {
        state.count = 0;
        state.until = Date.now() + LOCKOUT_MS;
    }
    sessionStorage.setItem(ATTEMPT_KEY, JSON.stringify(state));
    return state;
}

function login(username, password, remember) {
    const state = readAttempts();
    const wait = Math.ceil((state.until - Date.now()) / 1000);
    if (wait > 0) {
        return {
            ok: false,
            message: "Too many attempts. Try again in " + wait + " seconds."
        };
    }

    const name = String(username || "").trim().toLowerCase();
    const secret = String(password || "");
    const hash = name.length > 0 && name.length <= 40 && secret.length > 0 && secret.length <= 72
        ? sha256(secret)
        : null;
    const account = hash
        ? ACCOUNTS.find(function (candidate) {
            return candidate.username === name && hashesMatch(candidate.passwordHash, hash);
        })
        : null;

    if (!account) {
        recordFailure();
        return { ok: false, message: "Invalid username or password." };
    }

    sessionStorage.removeItem(ATTEMPT_KEY);
    const lifetime = remember ? REMEMBER_SECONDS : SESSION_SECONDS;
    const expiry = Math.floor(Date.now() / 1000) + lifetime;
    const payload = account.username + "|" + account.rank + "|" + expiry;
    const signature = sha256(payload + "|" + SESSION_SECRET);
    writeCookie(SESSION_COOKIE, payload + "|" + signature, remember ? lifetime : undefined);
    deleteCookie("username");
    return { ok: true };
}

function logout() {
    deleteCookie(SESSION_COOKIE);
    deleteCookie("username");
    sessionStorage.removeItem(RETURN_KEY);
}

function readSession() {
    const raw = getCookie(SESSION_COOKIE);
    if (!raw) {
        return null;
    }
    const parts = raw.split("|");
    if (parts.length !== 4) {
        return null;
    }
    const username = parts[0];
    const rank = parts[1];
    const expiry = parts[2];
    const signature = parts[3];
    if (!/^\d+$/.test(expiry) || Number(expiry) < Math.floor(Date.now() / 1000)) {
        return null;
    }
    const expected = sha256(username + "|" + rank + "|" + expiry + "|" + SESSION_SECRET);
    if (!expected || !hashesMatch(expected, signature)) {
        return null;
    }
    return ACCOUNTS.find(function (account) {
        return account.username === username && account.rank === rank;
    }) || null;
}

function siteRelativePath() {
    let path = "";
    try {
        path = decodeURIComponent(location.pathname);
    } catch (error) {
        path = location.pathname;
    }
    path = path.replace(/\\/g, "/");
    const marker = "CSCI3000WebsiteProject/";
    const markerIndex = path.toLowerCase().indexOf(marker.toLowerCase());
    if (markerIndex !== -1) {
        path = path.slice(markerIndex + marker.length);
    } else {
        path = path.replace(/^\/+/, "");
    }
    if (!path || path.endsWith("/")) {
        path += "index.html";
    }
    return path;
}

function safeReturn(path) {
    if (typeof path !== "string" || path.length < 1 || path.length > 200) {
        return "index.html";
    }
    if (!/^[A-Za-z0-9./_-]+$/.test(path) || path.includes("..") || path.includes("//") || path.startsWith("/")) {
        return "index.html";
    }
    if (!path.endsWith(".html")) {
        return "index.html";
    }
    return path;
}

function rememberReturnPath() {
    sessionStorage.setItem(RETURN_KEY, safeReturn(siteRelativePath()));
}

function consumeReturnPath() {
    const destination = safeReturn(sessionStorage.getItem(RETURN_KEY));
    sessionStorage.removeItem(RETURN_KEY);
    return destination;
}

function loginHref() {
    const depth = siteRelativePath().split("/").length - 1;
    return "../".repeat(depth) + "login.html";
}

function fileFromHref(href) {
    if (!href || href.startsWith("#") || href.startsWith("mailto:")) {
        return "";
    }
    const clean = href.split("?")[0].split("#")[0];
    const file = clean.split("/").pop();
    return file || "";
}

function showGate(requiredLevel) {
    const content = document.querySelector(".content");
    if (!content) {
        return;
    }
    rememberReturnPath();
    const required = rankLabel(rankIdForLevel(requiredLevel));
    const panel = document.createElement("div");
    panel.className = "access-gate";

    const heading = document.createElement("h2");
    heading.textContent = "Members only";

    const message = document.createElement("p");
    if (currentSession) {
        message.textContent = "This page is for " + required + " and above. You are signed in as " + rankLabel(currentSession.rank) + ".";
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
    const level = currentSession ? rankLevel(currentSession.rank) : 0;
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
    greeting.append(document.createTextNode(
        "Hello, " + currentSession.displayName + " (" + rankLabel(currentSession.rank) + ")! "
    ));
    const button = document.createElement("button");
    button.type = "button";
    button.className = "logout-button";
    button.textContent = "Log out";
    button.addEventListener("click", function () {
        logout();
        window.location.reload();
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

function updateMenu() {
    const level = currentSession ? rankLevel(currentSession.rank) : 0;
    document.querySelectorAll("a[href]").forEach(function (anchor) {
        const href = anchor.getAttribute("href");
        const file = fileFromHref(href);
        if (file === "login.html") {
            if (!currentSession) {
                return;
            }
            anchor.textContent = "Log out";
            anchor.addEventListener("click", function (event) {
                event.preventDefault();
                logout();
                window.location.reload();
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
    const level = currentSession ? rankLevel(currentSession.rank) : 0;
    if (required > level) {
        showGate(required);
        return;
    }
    gateSections();
}

let currentSession = null;

function initPage() {
    deleteCookie("username");
    currentSession = readSession();
    ensureGreeting();
    renderGreeting();
    updateMenu();
    protectPage();
}

function onReady(callback) {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", callback);
    } else {
        callback();
    }
}

if (typeof document !== "undefined") {
    onReady(initPage);
}

window.CKAF = {
    login: login,
    logout: logout,
    consumeReturnPath: consumeReturnPath
};
