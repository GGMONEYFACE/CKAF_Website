const form = document.getElementById("reset-form");
const note = document.getElementById("reset-note");
const messageEl = document.getElementById("login-error");
const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
const query = new URLSearchParams(window.location.search);
const tokenType = hash.get("type") || "";
const recoveryToken = hash.get("access_token") || "";

if (window.history.replaceState) {
    window.history.replaceState(null, "", window.location.pathname);
}

function showResetMessage(message, ok) {
    if (note && !ok) {
        note.textContent = message;
    }
    if (!messageEl) {
        return;
    }
    messageEl.textContent = message;
    messageEl.classList.toggle("success", Boolean(ok));
    messageEl.classList.add("visible");
}

if (query.get("error") || query.get("error_code")) {
    showResetMessage("This reset link has expired. Request a new one.");
} else if (tokenType === "recovery" && recoveryToken) {
    if (note) {
        note.textContent = "Choose a new password for your member account.";
    }
    form.hidden = false;
} else {
    showResetMessage("Open the reset link from your email to choose a new password.");
}

if (form && !form.hidden) {
    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const button = form.querySelector(".login-button");
        const password = document.getElementById("password").value;
        const confirm = document.getElementById("confirm").value;
        messageEl.classList.remove("visible", "success");
        if (password !== confirm) {
            showResetMessage("Those passwords do not match.");
            return;
        }
        button.disabled = true;
        try {
            const response = await fetch("/api/reset", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    token: recoveryToken,
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
                showResetMessage(result.message || "That password was not saved.");
                document.getElementById("password").value = "";
                document.getElementById("confirm").value = "";
                button.disabled = false;
                return;
            }
            window.location.href = result.redirect || "login.html";
        } catch (error) {
            showResetMessage("Password reset is unavailable. Reload the page and try again.");
            button.disabled = false;
        }
    });
}
