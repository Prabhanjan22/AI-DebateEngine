const API_BASE = "http://localhost:8000/api";

// ── DOM refs ───────────────────────────────────────────────────────────────────
const setupScreen    = document.getElementById("setup-screen");
const debateScreen   = document.getElementById("debate-screen");
const setupForm      = document.getElementById("setup-form");
const topicInput     = document.getElementById("topic");
const roundsInput    = document.getElementById("rounds");
const startBtn       = document.getElementById("start-btn");

const displayTopic   = document.getElementById("display-topic");
const displayRound   = document.getElementById("display-round");
const displayTotal   = document.getElementById("display-total-rounds");
const debateStatus   = document.getElementById("debate-status");
const chatContainer  = document.getElementById("chat-container");

const userInputArea  = document.getElementById("user-input-area");
const userMessage    = document.getElementById("user-message");
const sendBtn        = document.getElementById("send-btn");

const verdictModal   = document.getElementById("verdict-modal");
const verdictWinner  = document.getElementById("verdict-winner");
const verdictReason  = document.getElementById("verdict-reasoning");
const restartBtn     = document.getElementById("restart-btn");
const traceFromModalBtn = document.getElementById("trace-from-modal-btn");

const traceBtn       = document.getElementById("trace-btn");
const traceModal     = document.getElementById("trace-modal");
const traceContent   = document.getElementById("trace-content");
const closeTraceBtn  = document.getElementById("close-trace-btn");

const msgTemplate    = document.getElementById("message-template");

// ── State ──────────────────────────────────────────────────────────────────────
let debateId   = null;
let loopActive = false;

// ── Utility: fetch with timeout ────────────────────────────────────────────────
// Helper function to handle API requests with automatic timeouts
async function apiFetch(path, opts = {}, timeoutMs = 90000) {
    const ctrl  = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
        const res = await fetch(API_BASE + path, { ...opts, signal: ctrl.signal });
        clearTimeout(timer);
        const json = await res.json();
        if (!res.ok) throw new Error(json.detail || `HTTP ${res.status}`);
        return json;
    } catch (err) {
        clearTimeout(timer);
        if (err.name === "AbortError")
            throw new Error("Timed out waiting for AI — retrying...");
        throw err;
    }
}

function setStatus(msg, isErr = false) {
    debateStatus.textContent = msg;
    debateStatus.style.background = isErr ? "rgba(239,68,68,0.25)" : "";
    debateStatus.style.color      = isErr ? "#f87171" : "";
}

// ── Start debate ───────────────────────────────────────────────────────────────
setupForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const topic  = topicInput.value.trim();
    const rounds = parseInt(roundsInput.value, 10) || 2;
    if (!topic) { topicInput.focus(); return; }

    startBtn.disabled = true;
    startBtn.querySelector("span").textContent = "Initializing…";

    try {
        const data = await apiFetch("/start_debate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ topic, total_rounds: rounds }),
        }, 30000);

        debateId   = data.debate_id;
        loopActive = true;

        setupScreen.classList.add("hidden");
        debateScreen.classList.remove("hidden");

        displayTopic.textContent = data.topic;
        displayTotal.textContent = data.total_rounds;
        displayRound.textContent = "1";
        traceBtn.classList.remove("hidden");

        addMessage({ speaker: "SYSTEM", content: data.message });
        processNextTurn();

    } catch (err) {
        setStatus("Failed to start: " + err.message, true);
        startBtn.disabled = false;
        startBtn.querySelector("span").textContent = "Initialize Debate";
    }
});

// ── AI auto-loop ───────────────────────────────────────────────────────────────
async function processNextTurn() {
    if (!debateId || !loopActive) return;
    setStatus("AI is thinking…");

    try {
        const data = await apiFetch("/next_turn", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ debate_id: debateId }),
        });
        handleResponse(data);
    } catch (err) {
        setStatus(err.message + " — retrying in 4 s", true);
        setTimeout(() => { if (loopActive) processNextTurn(); }, 4000);
    }
}

// ── Handle any /next_turn response ─────────────────────────────────────────────
// Processes the engine's response and updates UI state accordingly
function handleResponse(data) {
    const status = data.status;  // "active" | "waiting_for_user" | "finished"
    const turn   = data.turn;    // who speaks NEXT: "PRO" | "AGAINST" | "USER" | "DONE"

    // Always render the message (unless it's the bare "it's your turn" prompt)
    if (data.speaker !== "SYSTEM") {
        addMessage(data);
        displayRound.textContent = data.round;
    }

    if (status === "finished") {
        loopActive = false;
        setStatus("Debate finished — judging…");
        runArbiter();

    } else if (status === "waiting_for_user" || turn === "USER") {
        // ← THIS was the bug: old code only showed input if speaker === "SYSTEM"
        setStatus("Your turn — type your argument below");
        userInputArea.classList.remove("hidden");
        userMessage.focus();
        sendBtn.disabled = false;

    } else {
        // Next turn is another AI agent — keep the loop going
        setTimeout(processNextTurn, 900);
    }
}

// ── User submits argument ──────────────────────────────────────────────────────
async function submitUserTurn() {
    const text = userMessage.value.trim();
    if (!text || !debateId) return;

    sendBtn.disabled     = true;
    userMessage.disabled = true;
    userInputArea.classList.add("hidden");
    setStatus("Processing your argument…");

    try {
        const data = await apiFetch("/next_turn", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ debate_id: debateId, user_input: text }),
        });
        userMessage.value    = "";
        userMessage.disabled = false;
        loopActive = true;
        handleResponse(data);
    } catch (err) {
        setStatus("Error: " + err.message, true);
        userInputArea.classList.remove("hidden");
        userMessage.disabled = false;
        sendBtn.disabled     = false;
    }
}

sendBtn.addEventListener("click", submitUserTurn);
userMessage.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitUserTurn(); }
});

// ── Arbiter ────────────────────────────────────────────────────────────────────
// Triggers the final debate evaluation and displays the verdict
async function runArbiter() {
    try {
        const data = await apiFetch(
            `/end_debate?debate_id=${debateId}`, {}, 60000
        );
        const v = data.verdict;
        verdictWinner.textContent = `WINNER: ${v.winner}`;
        verdictWinner.setAttribute("data-winner", v.winner);
        verdictReason.textContent = v.reasoning;
        setTimeout(() => verdictModal.classList.remove("hidden"), 800);
    } catch (err) {
        setStatus("Arbiter error: " + err.message, true);
    }
}

// ── Restart ────────────────────────────────────────────────────────────────────
restartBtn.addEventListener("click", () => {
    loopActive = false;
    debateId   = null;
    chatContainer.innerHTML  = "";
    topicInput.value         = "";
    roundsInput.value        = "2";
    userMessage.value        = "";
    userInputArea.classList.add("hidden");
    verdictModal.classList.add("hidden");
    traceModal.classList.add("hidden");
    traceBtn.classList.add("hidden");
    debateScreen.classList.add("hidden");
    setupScreen.classList.remove("hidden");
    startBtn.disabled = false;
    startBtn.querySelector("span").textContent = "Initialize Debate";
    setStatus("Initializing…");
});

// ── Trace Handling ─────────────────────────────────────────────────────────────
async function loadAndShowTrace() {
    if (!debateId) return;
    traceContent.textContent = "Loading trace data...";
    traceModal.classList.remove("hidden");
    
    try {
        const data = await apiFetch(`/trace?debate_id=${debateId}`);
        let output = `Debate ID: ${data.debate_id}\nTopic: ${data.topic}\nTotal Embedded Docs: ${data.total_turns_recorded}\n\n`;
        
        output += `=== FULL EVENT HISTORY (Includes Evaluators) ===\n\n`;
        data.history.forEach((msg, idx) => {
            output += `[Event ${idx + 1}] Role: ${msg.role}\n`;
            output += `Content: ${msg.content}\n`;
            output += `--------------------------------------------------\n`;
        });

        output += `\n=== FAISS DOCUMENT STORE (RAG Embeddings) ===\n\n`;
        data.docs.forEach(doc => {
            output += `[Doc ID: ${doc.id} | Speaker: ${doc.speaker} | Round: ${doc.round_num}]\n`;
            output += `Vector Text: ${doc.text}\n`;
            output += `Raw Content: ${doc.raw_content}\n`;
            output += `--------------------------------------------------\n`;
        });
        
        traceContent.textContent = output;
    } catch (err) {
        traceContent.textContent = "Error loading trace: " + err.message;
    }
}

traceBtn.addEventListener("click", loadAndShowTrace);
traceFromModalBtn.addEventListener("click", () => {
    verdictModal.classList.add("hidden");
    loadAndShowTrace();
});
closeTraceBtn.addEventListener("click", () => {
    traceModal.classList.add("hidden");
    // If the debate has finished, closing the trace should bring back the verdict modal
    if (!loopActive && debateId) {
        verdictModal.classList.remove("hidden");
    }
});

// ── Render a message bubble ────────────────────────────────────────────────────
function addMessage(data) {
    const clone   = msgTemplate.content.cloneNode(true);
    const wrapper = clone.querySelector(".message-wrapper");

    // CSS class for speaker-specific styling
    const cls = (data.speaker || "system").toLowerCase().replace(/[^a-z]/g, "");
    wrapper.classList.add(cls);

    clone.querySelector(".message-avatar").textContent  =
        (data.speaker || "?").charAt(0).toUpperCase();
    clone.querySelector(".message-speaker").textContent = data.speaker;
    clone.querySelector(".message-text").textContent    = data.content;

    // Fact-check badge
    if (data.fact_check?.assessment) {
        const fc  = clone.querySelector(".fact-check");
        const map = { TRUE: "✓", FALSE: "✕", MIXED: "⚠", OPINION: "💭", UNVERIFIED: "?" };
        fc.classList.remove("hidden");
        fc.setAttribute("data-assessment", data.fact_check.assessment);
        clone.querySelector(".fc-assessment").textContent =
            `${map[data.fact_check.assessment] ?? "?"} ${data.fact_check.assessment}`;
        clone.querySelector(".fc-tooltip").textContent =
            `${data.fact_check.reasoning} (Confidence: ${data.fact_check.confidence}%)`;
    }

    // Score badge
    if (data.score?.overall !== undefined) {
        const sc = clone.querySelector(".score");
        sc.classList.remove("hidden");
        clone.querySelector(".score-overall").textContent = `★ ${data.score.overall}/10`;
        clone.querySelector(".score-logic").textContent   = data.score.logic;
        clone.querySelector(".score-rel").textContent     = data.score.relevance;
        clone.querySelector(".score-pers").textContent    = data.score.persuasiveness;
        clone.querySelector(".score-reason").textContent  = data.score.reasoning;
    }

    chatContainer.appendChild(wrapper);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}
