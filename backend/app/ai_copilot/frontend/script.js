const API_URL = "http://127.0.0.1:8000/api/v1/copilot/chat";

let sessionId = null;
let isLoading = false;

const chatInput = document.getElementById("userInput");
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const sendButton = document.getElementById("sendButton");
const connectionStatus = document.getElementById("connectionStatus");

// Add a message to the chat
function addMessage(message, sender = "bot") {
    const messageDiv = document.createElement("div");

    messageDiv.className =
        sender === "user"
            ? "message user-message"
            : "message assistant-message";

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = sender === "user" ? "👩‍🚀" : "🌙";

    const content = document.createElement("div");
    content.className = "message-content";

    const name = document.createElement("strong");
    name.textContent =
        sender === "user" ? "MISSION OPERATOR" : "LUNA-SCOPE AI";

    const text = document.createElement("p");
    text.textContent = message;

    content.appendChild(name);
    content.appendChild(text);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageDiv;
}

// Check backend connection
async function checkBackend() {
    try {
        const response = await fetch("http://127.0.0.1:8000/health");

        if (!response.ok) {
            throw new Error("Backend unavailable");
        }

        if (connectionStatus) {
            connectionStatus.textContent = "Connected";
        }
    } catch (error) {
        if (connectionStatus) {
            connectionStatus.textContent = "Disconnected";
        }
    }
}

// Send question to FastAPI
async function sendQuestion(question) {
    if (!question || isLoading) return;

    isLoading = true;
    addMessage(question, "user");

    chatInput.value = "";
    sendButton.disabled = true;

    const loading = addMessage(
        "Analyzing your mission question...",
        "bot"
    );

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                question: question,
                session_id: sessionId
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }

        loading.remove();

        if (data.session_id) {
            sessionId = data.session_id;
        }

        if (data.success) {
            addMessage(
                data.answer || "No answer was returned.",
                "bot"
            );
        } else {
            addMessage(
                data.error || "Unable to process your question.",
                "bot"
            );
        }

    } catch (error) {
        loading.remove();

        console.error("Copilot error:", error);

        addMessage(
            "Unable to connect to the Copilot backend. " +
            "Check that FastAPI is running at 127.0.0.1:8000. " +
            "Details: " + error.message,
            "bot"
        );

    } finally {
        isLoading = false;
        sendButton.disabled = false;
        chatInput.focus();
    }
}

// Chat form submission
chatForm.addEventListener("submit", function(event) {
    event.preventDefault();
    sendQuestion(chatInput.value.trim());
});

// Suggested questions
document.querySelectorAll(".suggestion-btn").forEach(button => {
    button.addEventListener("click", function() {
        const question = this.dataset.question;
        sendQuestion(question);
    });
});

// Check backend on page load
checkBackend();

console.log("LUNA-SCOPE Mission Copilot initialized.");