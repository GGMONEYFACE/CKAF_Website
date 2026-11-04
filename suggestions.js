const form = document.querySelector(".login-form");
const messageEl = document.getElementById("login-error");
const submitButton = form.querySelector(".login-button");
const suggestionField = document.getElementById("suggestion");

function showSuggestionMessage(message, ok) {
    messageEl.textContent = message;
    messageEl.classList.toggle("success", Boolean(ok));
    messageEl.classList.add("visible");
}

form.addEventListener("submit", async function (event) {
    event.preventDefault();
    messageEl.classList.remove("visible", "success");
    if (!suggestionField.value.trim()) {
        showSuggestionMessage("Write a suggestion first.");
        return;
    }
    submitButton.disabled = true;
    try {
        const response = await fetch("/api/suggestions", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: document.getElementById("name").value,
                message: suggestionField.value,
                company: document.getElementById("company").value
            })
        });
        let result = {};
        try {
            result = await response.json();
        } catch (error) {
            result = {};
        }
        if (!response.ok) {
            showSuggestionMessage(result.message || "That suggestion was not saved. Reload the page and try again.");
            submitButton.disabled = false;
            return;
        }
        suggestionField.value = "";
        showSuggestionMessage(result.message || "Thanks. An instructor can read that suggestion.", true);
    } catch (error) {
        showSuggestionMessage("That suggestion was not saved. Reload the page and try again.");
    }
    submitButton.disabled = false;
});
