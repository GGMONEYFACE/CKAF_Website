const BELTS = {
    white: "White Belt",
    "10th": "10th Gold",
    "9th": "9th Purple",
    "8th": "8th Orange",
    "7th": "7th Blue",
    "6th": "6th Green",
    "5th": "5th Green",
    "4th": "4th Brown",
    "3rd": "3rd Brown",
    "2nd": "2nd Red",
    "1st": "1st Red",
    black: "Black Belt"
};

const form = document.querySelector(".login-form");
const messageEl = document.getElementById("login-error");
const nameInput = document.getElementById("account-name");
const heading = document.getElementById("member-heading");
const beltEl = document.getElementById("member-belt");

function showAccountMessage(message, ok) {
    if (!messageEl) {
        return;
    }
    messageEl.textContent = message;
    messageEl.classList.toggle("success", Boolean(ok));
    messageEl.classList.add("visible");
}

function showMember(data) {
    const name = data && typeof data.displayName === "string" ? data.displayName : "";
    if (heading && name) {
        heading.textContent = name;
    }
    if (nameInput && name) {
        nameInput.value = name;
    }
    if (beltEl) {
        const label = data && BELTS[data.rank] ? BELTS[data.rank] : "Belt not set";
        beltEl.textContent = label;
    }
}

async function loadAccount() {
    if (!form) {
        return;
    }
    try {
        const response = await fetch("/api/me", { credentials: "same-origin" });
        if (!response.ok) {
            return;
        }
        showMember(await response.json());
    } catch (error) {
        showAccountMessage("Your member page is unavailable. Reload and try again.");
    }
}

if (form && typeof window.ckafReadSession === "function") {
    const cached = window.ckafReadSession();
    if (cached) {
        showMember(cached);
    }
}

const passwordForm = document.getElementById("password-form");
const passwordMessage = document.getElementById("password-message");

function showPasswordMessage(message, ok) {
    if (!passwordMessage) {
        return;
    }
    passwordMessage.textContent = message;
    passwordMessage.classList.toggle("success", Boolean(ok));
    passwordMessage.classList.add("visible");
}

if (passwordForm) {
    passwordForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        const button = passwordForm.querySelector(".login-button");
        const current = document.getElementById("current-password").value;
        const password = document.getElementById("new-password").value;
        const confirm = document.getElementById("confirm-password").value;
        passwordMessage.classList.remove("visible", "success");
        if (password !== confirm) {
            showPasswordMessage("Those passwords do not match.");
            return;
        }
        button.disabled = true;
        try {
            const response = await fetch("/api/account/password", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    current: current,
                    password: password,
                    confirm: confirm
                })
            });
            let result = {};
            try {
                result = await response.json();
            } catch (error) {
                result = {};
            }
            if (!response.ok) {
                showPasswordMessage(result.message || "That password was not changed.");
                document.getElementById("current-password").value = "";
                button.disabled = false;
                return;
            }
            if (result.redirect) {
                window.location.href = result.redirect;
                return;
            }
            passwordForm.reset();
            showPasswordMessage("Your password was changed.", true);
        } catch (error) {
            showPasswordMessage("Your member page is unavailable. Reload and try again.");
        }
        button.disabled = false;
    });
}

if (form) {
    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const button = form.querySelector(".login-button");
        button.disabled = true;
        messageEl.classList.remove("visible", "success");
        try {
            const response = await fetch("/api/account/name", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: nameInput.value })
            });
            let result = {};
            try {
                result = await response.json();
            } catch (error) {
                result = {};
            }
            if (!response.ok) {
                showAccountMessage(result.message || "That name was not saved.");
                button.disabled = false;
                return;
            }
            window.location.reload();
        } catch (error) {
            showAccountMessage("Your member page is unavailable. Reload and try again.");
        }
        button.disabled = false;
    });
    if (!nameInput.value) {
        loadAccount();
    }
}
