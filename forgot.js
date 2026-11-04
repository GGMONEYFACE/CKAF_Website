const form = document.querySelector(".login-form");
const messageEl = document.getElementById("login-error");
const submitButton = form.querySelector(".login-button");

function showForgotMessage(message, ok) {
    messageEl.textContent = message;
    messageEl.classList.toggle("success", Boolean(ok));
    messageEl.classList.add("visible");
}

form.addEventListener("submit", async function (event) {
    event.preventDefault();
    messageEl.classList.remove("visible", "success");
    submitButton.disabled = true;
    try {
        const response = await fetch("/api/forgot", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: document.getElementById("email").value })
        });
        let result = {};
        try {
            result = await response.json();
        } catch (error) {
            result = {};
        }
        if (!response.ok) {
            showForgotMessage(result.message || "Password reset is unavailable. Reload the page and try again.");
            submitButton.disabled = false;
            return;
        }
        showForgotMessage(result.message || "If that email belongs to a member, a reset link is on its way.", true);
    } catch (error) {
        showForgotMessage("Password reset is unavailable. Reload the page and try again.");
    }
    submitButton.disabled = false;
});
