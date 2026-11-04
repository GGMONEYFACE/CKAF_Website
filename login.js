const loginForm = document.querySelector(".login-form");
const errorEl = document.getElementById("login-error");

function showLoginError(message) {
    errorEl.textContent = message;
    errorEl.classList.add("visible");
}

loginForm.addEventListener("submit", function (event) {
    event.preventDefault();
    errorEl.textContent = "";
    errorEl.classList.remove("visible");

    if (!window.CKAF) {
        showLoginError("Sign-in is unavailable. Reload the page.");
        return;
    }

    const username = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    const remember = document.getElementById("remember").checked;
    const result = window.CKAF.login(username, password, remember);

    if (!result.ok) {
        showLoginError(result.message);
        document.getElementById("password").value = "";
        return;
    }

    window.location.href = window.CKAF.consumeReturnPath();
});
