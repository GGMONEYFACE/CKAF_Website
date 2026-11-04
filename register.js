const registerForm = document.querySelector(".login-form");
const errorEl = document.getElementById("login-error");
const submitButton = registerForm.querySelector(".login-button");

function showRegisterMessage(message, ok) {
    errorEl.textContent = message;
    errorEl.classList.toggle("success", Boolean(ok));
    errorEl.classList.add("visible");
}

registerForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    errorEl.textContent = "";
    errorEl.classList.remove("visible", "success");
    const name = document.getElementById("name").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    const confirm = document.getElementById("confirm").value;
    if (password !== confirm) {
        showRegisterMessage("Those passwords do not match.");
        return;
    }
    submitButton.disabled = true;

    try {
        const response = await fetch("/api/register", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: name,
                email: email,
                password: password
            })
        });
        let result = {};
        try {
            result = await response.json();
        } catch (error) {
            result = {};
        }
        if (!response.ok) {
            showRegisterMessage(result.message || "Registration was rejected.");
            document.getElementById("password").value = "";
            document.getElementById("confirm").value = "";
            submitButton.disabled = false;
            return;
        }
        if (result.redirect) {
            window.location.href = "index.html";
            return;
        }
        showRegisterMessage(result.message || "Check your email for a confirmation link, then sign in.", true);
        submitButton.disabled = false;
    } catch (error) {
        showRegisterMessage("Registration is unavailable. Reload the page and try again.");
        submitButton.disabled = false;
    }
});
