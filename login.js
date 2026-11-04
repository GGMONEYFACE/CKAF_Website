const loginForm = document.querySelector(".login-form");
const errorEl = document.getElementById("login-error");
const submitButton = loginForm.querySelector(".login-button");

function showLoginError(message) {
    errorEl.textContent = message;
    errorEl.classList.add("visible");
}

function safeRedirect(path) {
    if (typeof path !== "string" || path.length < 1 || path.length > 200) {
        return "index.html";
    }
    if (!/^[A-Za-z0-9./_-]+$/.test(path) || path.includes("..") || path.startsWith("/") || path.startsWith(".")) {
        return "index.html";
    }
    if (!path.endsWith(".html")) {
        return "index.html";
    }
    return path;
}

loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    errorEl.textContent = "";
    errorEl.classList.remove("visible");
    submitButton.disabled = true;

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    const remember = document.getElementById("remember").checked;
    const next = new URLSearchParams(window.location.search).get("next");

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email: email,
                password: password,
                remember: remember,
                next: next
            })
        });
        let result = {};
        try {
            result = await response.json();
        } catch (error) {
            result = {};
        }
        if (!response.ok) {
            showLoginError(result.message || "Invalid email or password.");
            document.getElementById("password").value = "";
            submitButton.disabled = false;
            return;
        }
        window.location.href = safeRedirect(result.redirect);
    } catch (error) {
        showLoginError("Sign-in is unavailable. Reload the page and try again.");
        submitButton.disabled = false;
    }
});
