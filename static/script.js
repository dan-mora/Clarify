let conversationId = null;
let privateSession = null;
let isLoading = false;

// Word-by-word rendering buffer
let wordQueue = [];
let wordTimer = null;
const WORD_DELAY_MS = 40;

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
    const loadingEl = appendMessage("assistant", "", true);

    try {
        const body = { message: text };
        if (conversationId) {
            body.conversation_id = conversationId;
        } else {
            body.private_session = privateSession;
        }

        const res = await fetch("/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });

        if (!res.ok) throw new Error("Request failed");

        loadingEl.classList.remove("loading");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        wordQueue = [];

        function startDrain() {
            if (wordTimer) return;
            wordTimer = setInterval(() => {
                if (wordQueue.length === 0) {
                    clearInterval(wordTimer);
                    wordTimer = null;
                    return;
                }
                loadingEl.textContent += wordQueue.shift();
                scrollToBottom();
            }, WORD_DELAY_MS);
        }

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Parse complete SSE messages out of the buffer
            const parts = buffer.split("\n\n");
            buffer = parts.pop(); // keep the incomplete trailing chunk

            for (const part of parts) {
                const eventMatch = part.match(/^event: (.+)$/m);
                const dataMatch = part.match(/^data: (.+)$/m);
                if (!eventMatch || !dataMatch) continue;

                const eventType = eventMatch[1];
                const data = JSON.parse(dataMatch[1]);

                if (eventType === "conversation_id") {
                    conversationId = data.conversation_id;
                } else if (eventType === "text_delta") {
                    // Split into words, preserving whitespace before each word
                    const words = data.text.match(/\s*\S+|\s+/g);
                    if (words) {
                        wordQueue.push(...words);
                        startDrain();
                    }
                }
            }
        }

        // Wait for remaining words to finish rendering
        await new Promise((resolve) => {
            if (wordQueue.length === 0) return resolve();
            const check = setInterval(() => {
                if (wordQueue.length === 0) {
                    clearInterval(check);
                    resolve();
                }
            }, WORD_DELAY_MS);
        });
    } catch {
        wordQueue = [];
        clearInterval(wordTimer);
        wordTimer = null;
        loadingEl.textContent = "Sorry, something went wrong. Please try again.";
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

let scrollRAF = null;
function scrollToBottom() {
    if (scrollRAF) return;
    scrollRAF = requestAnimationFrame(() => {
        const container = document.getElementById("messages");
        container.scrollTop = container.scrollHeight;
        scrollRAF = null;
    });
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
