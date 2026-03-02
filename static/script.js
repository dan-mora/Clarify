let conversationId = null;
let privateSession = null;
let isLoading = false;

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btn-alone").addEventListener("click", () => startChat(true));
    document.getElementById("btn-not-alone").addEventListener("click", () => startChat(false));
    document.getElementById("btn-send").addEventListener("click", sendMessage);
    document.getElementById("btn-new-conversation").addEventListener("click", resetConversation);

    document.getElementById("message-input").addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});

function startChat(isPrivate) {
    privateSession = isPrivate;
    document.getElementById("landing-screen").classList.remove("active");
    document.getElementById("chat-screen").classList.add("active");
    document.getElementById("message-input").focus();
}

async function sendMessage() {
    const input = document.getElementById("message-input");
    const text = input.value.trim();
    if (!text || isLoading) return;

    isLoading = true;
    input.value = "";

    appendMessage("user", text);
    const loadingEl = appendMessage("assistant", "...", true);

    try {
        const body = { message: text };
        if (conversationId) {
            body.conversation_id = conversationId;
        } else {
            body.private_session = privateSession;
        }

        const res = await fetch("/chat/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });

        if (!res.ok) throw new Error("Request failed");

        const data = await res.json();
        conversationId = data.conversation_id;

        loadingEl.textContent = data.reply;
        loadingEl.classList.remove("loading");
    } catch {
        loadingEl.textContent = "Sorry, something went wrong. Please try again.";
        loadingEl.classList.remove("loading");
        loadingEl.classList.add("error");
    } finally {
        isLoading = false;
        scrollToBottom();
    }
}

function appendMessage(role, text, loading = false) {
    const container = document.getElementById("messages");
    const div = document.createElement("div");
    div.className = `message ${role}`;
    if (loading) div.classList.add("loading");
    div.textContent = text;
    container.appendChild(div);
    scrollToBottom();
    return div;
}

function scrollToBottom() {
    const container = document.getElementById("messages");
    container.scrollTop = container.scrollHeight;
}

async function resetConversation() {
    if (conversationId) {
        try {
            await fetch(`/chat/${conversationId}`, { method: "DELETE" });
        } catch {
            // Server-side data will be cleared on restart anyway
        }
    }

    conversationId = null;
    privateSession = null;
    isLoading = false;
    document.getElementById("messages").innerHTML = "";

    document.getElementById("chat-screen").classList.remove("active");
    document.getElementById("landing-screen").classList.add("active");
}
