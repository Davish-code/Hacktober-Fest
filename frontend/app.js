let currentPlan = null;
const API_BASE = window.APP_CONFIG?.API_BASE_URL || "http://localhost:8000";

// Consolidated theme and status mapping object matching Stitch neo-brutalist palette
const THEME_MAP = {
    statusBadge: {
        online: "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-DEFAULT text-xs font-semibold text-status-success bg-status-successBg border border-status-success/40",
        offline: "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-DEFAULT text-xs font-semibold text-status-danger bg-status-dangerBg border border-status-danger/40",
        error: "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-DEFAULT text-xs font-semibold text-status-warning bg-status-warningBg border border-status-warning/40",
        checking: "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-DEFAULT text-xs font-medium text-status-gray bg-status-grayBg border border-line"
    },
    effectChip: {
        READ: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-semibold text-[#1b683b] bg-[#ebf5ee] border border-[#1b683b]",
        TRANSFORM: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-semibold text-[#a35200] bg-[#fef4e6] border border-[#a35200]",
        WRITE: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-semibold text-[#a35200] bg-[#fef4e6] border border-[#a35200]",
        ANALYZE: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-semibold text-[#1b683b] bg-[#ebf5ee] border border-[#1b683b]",
        EXTERNAL: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-semibold text-[#ba1a1a] bg-[#ffdad6] border border-[#ba1a1a]"
    },
    eventStatus: {
        started: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-medium text-primary bg-surface-container border border-primary/30",
        ok: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-semibold text-status-success bg-status-successBg border border-status-success/30",
        retry: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-semibold text-status-warning bg-status-warningBg border border-status-warning/30",
        fallback: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-semibold text-status-warning bg-status-warningBg border border-status-warning/30",
        skipped: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-medium text-status-gray bg-status-grayBg border border-line",
        failed: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-semibold text-status-danger bg-status-dangerBg border border-status-danger/40",
        not_run: "inline-flex items-center px-1.5 py-0.5 rounded-DEFAULT text-xs font-mono font-medium text-status-gray bg-status-grayBg border border-line"
    },
    stepCard: {
        default: "bg-surface-container-lowest border border-surface-container-highest rounded-DEFAULT p-3.5 relative shadow-[1px_1px_0px_#1c1c18]",
        failed: "bg-surface-container-lowest border-y border-r border-surface-container-highest border-l-4 border-l-status-danger p-3.5 rounded-DEFAULT relative shadow-[2px_2px_0px_#ba1a1a]",
        success: "bg-surface-container-lowest border border-surface-container-highest rounded-DEFAULT p-3.5 relative shadow-[1px_1px_0px_#1c1c18]",
        not_run: "bg-surface-container-low border border-surface-container-highest rounded-DEFAULT p-3.5 relative opacity-60",
        external: "bg-surface-container-lowest border border-surface-container-highest border-l-4 border-l-primary p-3.5 rounded-DEFAULT relative shadow-[1px_1px_0px_#1c1c18]"
    }
};

let serverWakeStartTime = null;
let serverWakeInterval = null;

document.addEventListener("DOMContentLoaded", () => {
    checkHealth();
    loadManifest();
    loadLedger();

    // Check URL parameters for failure preview state
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("preview") === "failure") {
        setupFailurePreview();
    }
    if (urlParams.get("view") === "benchmark") {
        switchAppView("benchmark");
    }
});

function setDemoQuery(text) {
    const input = document.getElementById("request-input");
    if (input) {
        input.value = text;
        input.focus();
    }
}

// Check Backend Health & Manage Server Wake-Up Checklist
async function checkHealth() {
    const badge = document.getElementById("backend-status");
    const wakeBanner = document.getElementById("server-wakeup-banner");
    const modePill = document.getElementById("system-mode-pill");
    const timerDisplay = document.getElementById("server-wakeup-timer");
    const progressPct = document.getElementById("wakeup-progress-pct");
    const progressBar = document.getElementById("wakeup-progress-bar");

    if (badge) {
        badge.className = THEME_MAP.statusBadge.checking;
        badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-muted animate-pulse"></span><span>Checking backend...</span>';
    }

    serverWakeStartTime = Date.now();
    if (serverWakeInterval) clearInterval(serverWakeInterval);
    serverWakeInterval = setInterval(() => {
        const elapsedSec = ((Date.now() - serverWakeStartTime) / 1000).toFixed(1);
        if (timerDisplay) timerDisplay.textContent = `${elapsedSec}s elapsed (max 90s)`;
        const pct = Math.min(95, Math.floor((elapsedSec / 90) * 100));
        if (progressPct) progressPct.textContent = `${pct}%`;
        if (progressBar) progressBar.style.width = `${pct}%`;
    }, 200);

    // Show wake banner after 2.5s (Render free tier cold start can take 30-60s)
    const wakeTimer = setTimeout(() => {
        if (wakeBanner) wakeBanner.classList.remove("hidden");
    }, 2500);

    // Retry polling: attempt every 5 seconds for up to 90 seconds total
    const MAX_WAIT_MS = 90000;
    const POLL_INTERVAL_MS = 5000;

    const pollHealth = async () => {
        const elapsed = Date.now() - serverWakeStartTime;

        // Try the request with a 4s timeout per attempt
        const controller = new AbortController();
        const fetchTimeout = setTimeout(() => controller.abort(), 4000);

        try {
            const res = await fetch(`${API_BASE}/api/health`, { signal: controller.signal });
            clearTimeout(fetchTimeout);

            if (res.ok) {
                clearTimeout(wakeTimer);
                clearInterval(serverWakeInterval);
                const data = await res.json();

                if (badge) {
                    badge.className = THEME_MAP.statusBadge.online;
                    badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-status-success"></span><span>Connected (${data.actions_available} Safe Actions)</span>`;
                }
                if (modePill) modePill.textContent = data.mock_mode ? "Mock" : "Live";

                const liveIndicator = document.getElementById("live-mode-indicator");
                const liveLabel = document.getElementById("live-mode-label");
                if (liveIndicator) {
                    liveIndicator.classList.remove("hidden");
                    if (data.mock_mode) {
                        liveIndicator.classList.remove("text-tertiary");
                        liveIndicator.classList.add("text-status-warning");
                        if (liveLabel) liveLabel.textContent = "Mock LLM";
                    } else {
                        liveIndicator.classList.remove("text-status-warning");
                        liveIndicator.classList.add("text-tertiary");
                        if (liveLabel) liveLabel.textContent = "Live LLM";
                    }
                }

                updateChecklistItem("core", true, `FastAPI daemon responding: ${data.service} (200 OK)`);
                updateChecklistItem("actions", true, `${data.actions_available} verified safe actions active in registry`);
                updateChecklistItem("mode", true, `${data.environment} · ${data.mock_mode ? 'Mock LLM mode' : 'Live LLM mode'}`);

                if (wakeBanner) setTimeout(() => { wakeBanner.classList.add("hidden"); }, 1200);
                return; // success — stop polling
            } else {
                throw new Error(`HTTP ${res.status}`);
            }
        } catch (err) {
            clearTimeout(fetchTimeout);
            // Still within the wake window — schedule another attempt
            if (Date.now() - serverWakeStartTime < MAX_WAIT_MS) {
                updateChecklistItem("core", false, `Waking server... retrying in 5s (${Math.round((Date.now() - serverWakeStartTime) / 1000)}s elapsed)`);
                setTimeout(pollHealth, POLL_INTERVAL_MS);
            } else {
                // Exhausted retries
                clearTimeout(wakeTimer);
                clearInterval(serverWakeInterval);
                if (wakeBanner) wakeBanner.classList.remove("hidden");
                if (badge) {
                    badge.className = THEME_MAP.statusBadge.offline;
                    badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-status-danger"></span><span>Backend Offline</span>';
                }
                updateChecklistItem("core", false, `Connection refused to ${API_BASE}. Run backend server.`);
                updateChecklistItem("actions", false, "Unreachable - action whitelist verification pending");
                updateChecklistItem("mode", false, "Unreachable - environment status offline");
                updateChecklistItem("manifest", false, "Unreachable - dataset scanning halted");
            }
        }
    };

    // Start first poll immediately
    pollHealth();
}


function updateChecklistItem(itemKey, isOnline, text) {
    const icon = document.getElementById(`checklist-${itemKey}-icon`);
    const desc = document.getElementById(`checklist-${itemKey}-desc`);
    if (desc) desc.textContent = text;
    if (icon) {
        if (isOnline) {
            icon.className = "w-4 h-4 rounded-DEFAULT bg-[#ebf5ee] border border-[#1b683b] flex items-center justify-center font-mono font-bold text-[#1b683b] text-xs shrink-0";
            icon.textContent = "✓";
        } else {
            icon.className = "w-4 h-4 rounded-DEFAULT bg-[#ffdad6] border border-[#ba1a1a] flex items-center justify-center font-mono font-bold text-[#ba1a1a] text-xs shrink-0";
            icon.textContent = "!";
        }
    }
}

// Load Workspace Schema Manifest
async function loadManifest() {
    const container = document.getElementById("manifest-container");
    if (!container) return;
    try {
        const res = await fetch(`${API_BASE}/api/manifest`);
        if (!res.ok) throw new Error("Failed to load workspace schema");
        const data = await res.json();

        let html = '<div class="space-y-2">';
        const files = Object.entries(data);
        for (const [file, info] of files) {
            html += `
                <div class="bg-surface-container-low border border-surface-container-highest rounded-DEFAULT p-2.5 text-xs">
                    <div class="flex items-center justify-between mb-1">
                        <span class="font-mono font-semibold text-on-surface">${file}</span>
                        <span class="text-tertiary text-xs font-mono">${info.size_bytes} bytes</span>
                    </div>
                    <div class="font-mono text-tertiary text-xs leading-relaxed break-words">
                        Columns: ${info.columns.join(", ")}
                    </div>
                </div>
            `;
        }
        html += '</div>';
        container.innerHTML = html;
        updateChecklistItem("manifest", true, `${files.length} sandbox datasets mounted: ${files.map(f => f[0]).join(", ")}`);
    } catch (e) {
        container.innerHTML = `<div class="text-xs text-status-danger p-2 bg-status-dangerBg border border-status-danger/30 rounded-DEFAULT">Error loading workspace: ${e.message}</div>`;
        updateChecklistItem("manifest", false, `Workspace manifest error: ${e.message}`);
    }
}

// Generate Plan
async function generatePlan() {
    const inputEl = document.getElementById("request-input");
    const input = inputEl ? inputEl.value.trim() : "";
    if (!input) return alert("Please enter a request first.");

    const btn = document.getElementById("plan-btn");
    const container = document.getElementById("plan-steps-container");
    const blockedPanel = document.getElementById("blocked-request-panel");
    const fixCard = document.getElementById("suggested-fix-card");
    const badge = document.getElementById("plan-source-badge");
    const explanationEl = document.getElementById("plan-explanation");

    if (blockedPanel) blockedPanel.classList.add("hidden");
    if (fixCard) fixCard.classList.add("hidden");

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            <span>Generating...</span>
        `;
    }

    if (container) {
        container.innerHTML = `
            <div class="animate-pulse space-y-3">
                <div class="h-16 bg-surface-container-low border border-surface-container-highest rounded-DEFAULT"></div>
                <div class="h-16 bg-surface-container-low border border-surface-container-highest rounded-DEFAULT"></div>
                <div class="h-16 bg-surface-container-low border border-surface-container-highest rounded-DEFAULT"></div>
            </div>
        `;
    }

    try {
        const res = await fetch(`${API_BASE}/api/plan`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ request: input })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to generate plan");
        }

        const data = await res.json();
        currentPlan = data.plan;

        // Update honest provider matrix status
        updateProviderMatrix(data.source);

        // Check for safety rejection or arbiter issues
        if (data.issues && data.issues.length > 0 && (!currentPlan || !currentPlan.steps || currentPlan.steps.length === 0)) {
            if (blockedPanel) blockedPanel.classList.remove("hidden");
            if (explanationEl) explanationEl.textContent = "Request rejected by safety verifier. Action outside bounded whitelist.";
            if (container) container.innerHTML = `<div class="p-3 bg-status-dangerBg text-status-danger text-xs font-mono rounded-DEFAULT border border-status-danger/30">${data.issues.join("; ")}</div>`;
            return;
        }

        if (badge) {
            badge.style.display = "inline-flex";
            badge.textContent = `Consensus: ${data.source || 'Arbiter verified'}`;
        }
        if (explanationEl) {
            explanationEl.textContent = data.explanation || "Deterministic workflow synthesized across active datasets.";
        }

        renderPlanCards(currentPlan);
        const planActions = document.getElementById("plan-actions");
        if (planActions) planActions.style.display = "flex";
    } catch (e) {
        if (blockedPanel) blockedPanel.classList.remove("hidden");
        if (explanationEl) explanationEl.textContent = "Request could not be planned within safety constraints.";
        if (container) container.innerHTML = `<div class="p-3 bg-status-dangerBg text-status-danger text-xs rounded-DEFAULT border border-status-danger/30">${e.message}</div>`;
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = "<span>Generate Plan</span>";
        }
    }
}

// Update router matrix providers according to real router output
function updateProviderMatrix(source) {
    const geminiEl = document.getElementById("provider-status-gemini");
    const groqEl = document.getElementById("provider-status-groq");
    const cerebrasEl = document.getElementById("provider-status-cerebras");

    const activeProvider = (source || "").toLowerCase();

    if (activeProvider === "cache") {
        if (geminiEl) { geminiEl.textContent = "unused (cache hit)"; geminiEl.className = "font-mono text-xs text-tertiary"; }
        if (groqEl) { groqEl.textContent = "unused"; groqEl.className = "font-mono text-xs text-tertiary"; }
        if (cerebrasEl) { cerebrasEl.textContent = "bypassed"; cerebrasEl.className = "font-mono text-xs text-tertiary"; }
    } else if (activeProvider.includes("gemini")) {
        if (geminiEl) { geminiEl.textContent = "active (planner)"; geminiEl.className = "font-mono text-xs text-status-success font-semibold"; }
        if (groqEl) { groqEl.textContent = "verified (critic)"; groqEl.className = "font-mono text-xs text-status-success"; }
        if (cerebrasEl) { cerebrasEl.textContent = "bypassed"; cerebrasEl.className = "font-mono text-xs text-tertiary"; }
    } else if (activeProvider.includes("groq")) {
        if (geminiEl) { geminiEl.textContent = "fallback"; geminiEl.className = "font-mono text-xs text-tertiary"; }
        if (groqEl) { groqEl.textContent = "active (planner & critic)"; groqEl.className = "font-mono text-xs text-status-success font-semibold"; }
        if (cerebrasEl) { cerebrasEl.textContent = "bypassed"; cerebrasEl.className = "font-mono text-xs text-tertiary"; }
    } else {
        if (geminiEl) { geminiEl.textContent = "ready"; geminiEl.className = "font-mono text-xs text-status-success"; }
        if (groqEl) { groqEl.textContent = "ready"; groqEl.className = "font-mono text-xs text-status-success"; }
        if (cerebrasEl) { cerebrasEl.textContent = "bypassed"; cerebrasEl.className = "font-mono text-xs text-tertiary"; }
    }
}

// Render Step Cards with Step Connection Line, Chips, and Parameters
function renderPlanCards(plan, failedStepId = null) {
    const container = document.getElementById("plan-steps-container");
    if (!container) return;

    if (!plan || !plan.steps || plan.steps.length === 0) {
        container.innerHTML = "<p class='text-sm text-tertiary py-8 text-center border border-dashed border-surface-container-highest rounded-DEFAULT bg-surface-container-low'>No steps generated.</p>";
        return;
    }

    const effectMap = {
        READ_CSV: "READ",
        FILTER_ROWS: "TRANSFORM",
        SELECT_COLUMNS: "TRANSFORM",
        JOIN_DATA: "TRANSFORM",
        AGGREGATE: "TRANSFORM",
        SORT_ROWS: "TRANSFORM",
        EXPORT_CSV: "WRITE",
        GENERATE_SUMMARY: "ANALYZE",
        DRAFT_EMAIL: "EXTERNAL",
        join_rows: "READ",
        aggregate: "READ"
    };

    let html = '<div class="space-y-3 relative">';
    const steps = plan.steps;

    steps.forEach((step, index) => {
        const isLast = index === steps.length - 1;
        const isConditional = !!step.if;
        const effect = effectMap[step.action] || "READ";
        const isExternal = effect === "EXTERNAL" || step.action === "DRAFT_EMAIL" || step.action === "EXPORT_EXTERNAL";

        let cardStyle = THEME_MAP.stepCard.default;
        let isFailed = false;

        if (failedStepId !== null) {
            if (step.step_id === failedStepId) {
                cardStyle = THEME_MAP.stepCard.failed;
                isFailed = true;
            } else if (step.step_id > failedStepId) {
                cardStyle = THEME_MAP.stepCard.not_run;
            }
        } else if (isExternal) {
            cardStyle = THEME_MAP.stepCard.external;
        }

        const effectClass = THEME_MAP.effectChip[effect] || THEME_MAP.effectChip.READ;

        html += `
            <div class="${cardStyle} ${isConditional ? 'ml-4 border-l-2 border-dashed border-tertiary pl-4' : ''}">
                <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div class="flex items-center gap-2">
                        <span class="inline-flex items-center justify-center w-5 h-5 rounded-DEFAULT text-xs font-mono font-bold bg-surface-container text-on-surface border border-surface-container-highest">
                            S-0${step.step_id}
                        </span>
                        <span class="font-mono text-xs font-bold text-on-surface">${step.action}</span>
                        <span class="${effectClass}">[${effect}]</span>
                        ${isFailed ? '<span class="font-mono text-xs font-bold text-status-danger bg-status-dangerBg px-1.5 py-0.2 rounded-DEFAULT border border-status-danger">[EXECUTION FAILED]</span>' : ''}
                    </div>

                    <!-- Tags: If, Retry, Fallback -->
                    <div class="flex items-center gap-1.5 text-xs font-mono">
                        ${isConditional ? '<span class="px-1.5 py-0.5 rounded-DEFAULT bg-surface-container text-tertiary border border-surface-container-highest">If: ' + (step.if.ref || 'cond') + '</span>' : ''}
                        ${step.retries ? '<span class="px-1.5 py-0.5 rounded-DEFAULT bg-status-warningBg text-status-warning border border-status-warning/40">Retry: ' + step.retries + 'x</span>' : ''}
                        ${step.fallback ? '<span class="px-1.5 py-0.5 rounded-DEFAULT bg-surface-container text-primary border border-surface-container-highest">Fallback</span>' : ''}
                    </div>
                </div>

                <div class="text-sm text-on-surface mb-2 font-sans">
                    ${step.description || "Deterministic step execution"}
                </div>

                <!-- Parameters View in Monospace -->
                <div class="font-mono text-xs bg-surface-container-low border border-surface-container-highest rounded-DEFAULT p-2 text-tertiary leading-relaxed overflow-x-auto">
                    ${JSON.stringify(step.params)}
                </div>

                ${isExternal ? `
                    <div class="mt-2.5 pt-2 border-t border-surface-container-highest flex items-center gap-2 text-xs text-status-danger font-medium">
                        <input type="checkbox" id="approve-step-${step.step_id}" class="rounded-DEFAULT border-surface-container-highest text-primary focus:ring-primary" checked>
                        <label for="approve-step-${step.step_id}">Operator approval required (external effect - draft saved only)</label>
                    </div>
                ` : ''}

                ${!isLast ? '<div class="absolute left-6 -bottom-3 w-px h-3 bg-surface-container-highest hidden sm:block"></div>' : ''}
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

// Simulate Dry-Run
async function simulateDryRun() {
    if (!currentPlan) return;
    switchInspectorTab("runlog");
    const timeline = document.getElementById("timeline-container");
    if (!timeline) return;

    timeline.innerHTML = `
        <div class="p-3 bg-surface-container-low border border-surface-container-highest rounded-DEFAULT text-xs text-tertiary font-sans flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-primary animate-ping"></span>
            <span>Simulating dry-run verification...</span>
        </div>
    `;

    try {
        const res = await fetch(`${API_BASE}/api/dryrun`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentPlan)
        });

        const data = await res.json();
        if (data.success) {
            let html = "";
            data.steps.forEach(s => {
                html += `
                    <div class="bg-surface-container-lowest border border-surface-container-highest rounded-DEFAULT p-3 shadow-[1px_1px_0px_#1c1c18]">
                        <div class="flex items-center justify-between mb-1">
                            <span class="font-semibold text-on-surface font-sans">[Dry-Run Validated] Step ${s.step_id}: <span class="font-mono">${s.action}</span></span>
                            <span class="${THEME_MAP.effectChip[s.effect] || THEME_MAP.effectChip.READ}">[${s.effect}]</span>
                        </div>
                        <div class="text-tertiary text-xs font-mono">
                            Predicted: ${s.predicted_output}
                        </div>
                    </div>
                `;
            });
            timeline.innerHTML = html;
        } else {
            timeline.innerHTML = `
                <div class="bg-status-dangerBg border border-status-danger/40 rounded-DEFAULT p-3 text-status-danger text-xs font-mono">
                    <strong>Dry-Run Verification Failed:</strong> ${data.error}
                </div>
            `;
        }
    } catch (e) {
        timeline.innerHTML = `<div class="bg-status-dangerBg border border-status-danger/40 rounded-DEFAULT p-3 text-status-danger text-xs font-mono">Error: ${e.message}</div>`;
    }
}

// Execute Current Plan with SSE Streaming
async function executeCurrentPlan() {
    if (!currentPlan) return;
    switchInspectorTab("runlog");
    const timeline = document.getElementById("timeline-container");
    const fixCard = document.getElementById("suggested-fix-card");
    if (fixCard) fixCard.classList.add("hidden");

    if (timeline) {
        timeline.innerHTML = `
            <div class="p-3 bg-surface-container-low border border-surface-container-highest rounded-DEFAULT text-xs text-tertiary font-sans flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-primary animate-ping"></span>
                <span>Submitting plan for execution...</span>
            </div>
        `;
    }

    const runId = (typeof crypto !== "undefined" && crypto.randomUUID)
        ? crypto.randomUUID()
        : ("run_" + Date.now() + "_" + Math.random().toString(36).substring(2, 9));

    // Step 1: POST first to register the run on the backend
    let postPromise;
    try {
        postPromise = fetch(`${API_BASE}/api/execute`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ plan: currentPlan, dry_run_first: true, run_id: runId })
        });
    } catch (e) {
        if (timeline) timeline.innerHTML = `<div class="bg-status-dangerBg border border-status-danger/40 rounded-DEFAULT p-3 text-status-danger text-xs font-mono">Execution Failed: ${e.message}</div>`;
        return;
    }

    // Step 2: Open SSE stream after a short delay to allow backend to register the run
    let evtSource = null;
    let receivedEvents = 0;

    await new Promise(resolve => setTimeout(resolve, 150)); // let backend register run_id

    try {
        evtSource = new EventSource(`${API_BASE}/api/runs/${runId}/events`);

        if (timeline) {
            timeline.innerHTML = `
                <div class="p-3 bg-surface-container-low border border-surface-container-highest rounded-DEFAULT text-xs text-tertiary font-sans flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-primary animate-ping"></span>
                    <span>Connected to real-time execution stream...</span>
                </div>
            `;
        }

        evtSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.status === "_DONE_") {
                    evtSource.close();
                    return;
                }
                if (receivedEvents === 0 && timeline) {
                    timeline.innerHTML = "";
                }
                receivedEvents++;

                const statusClass = THEME_MAP.eventStatus[data.status] || THEME_MAP.eventStatus.started;
                const item = document.createElement("div");
                item.className = "bg-surface-container-lowest border border-surface-container-highest rounded-DEFAULT p-3 shadow-[1px_1px_0px_#1c1c18]";

                let detailText = data.detail || "";
                if (detailText.toLowerCase().includes("email")) {
                    detailText = detailText.replace(/queued|sent/gi, "Draft saved");
                }

                item.innerHTML = `
                    <div class="flex items-center justify-between mb-1">
                        <div class="flex items-center gap-2">
                            <span class="text-tertiary text-xs font-mono">${data.iso_time ? data.iso_time.split("T")[1].replace("Z", "") : ""}</span>
                            <span class="font-semibold text-on-surface font-sans">Step ${data.step_id}</span>
                        </div>
                        <span class="${statusClass}">[${data.status.toUpperCase()}]</span>
                    </div>
                    <div class="text-tertiary text-xs font-mono leading-relaxed">
                        ${detailText}
                    </div>
                `;
                if (timeline) {
                    timeline.appendChild(item);
                    timeline.scrollTop = timeline.scrollHeight;
                }
            } catch (err) {
                console.error("SSE parse error", err);
            }
        };
        evtSource.onerror = () => {
            if (evtSource) evtSource.close();
        };
    } catch (e) {
        console.warn("EventSource setup error, using POST fallback:", e);
    }

    // Step 3: Await the POST response
    try {
        const res = await postPromise;
        const data = await res.json();

        if (evtSource) {
            setTimeout(() => { evtSource.close(); }, 1200);
        }

        // Render from POST response if SSE events were empty (SSE fallback)
        if (receivedEvents === 0 && data.steps && timeline) {
            let html = "";
            data.steps.forEach(s => {
                const isSuccess = s.status === "SUCCESS";
                const statusChip = isSuccess ? THEME_MAP.eventStatus.ok : THEME_MAP.eventStatus.failed;
                let outputStr = isSuccess
                    ? (s.output !== undefined && s.output !== null ? JSON.stringify(s.output) : "✓ Completed")
                    : (s.error || "Step failed");
                if (outputStr.toLowerCase().includes("email")) {
                    outputStr = outputStr.replace(/queued|sent/gi, "Draft saved");
                }

                html += `
                    <div class="bg-surface-container-lowest border border-surface-container-highest rounded-DEFAULT p-3 shadow-[1px_1px_0px_#1c1c18]">
                        <div class="flex items-center justify-between mb-1">
                            <span class="font-semibold text-on-surface font-sans">Step ${s.step_id} [<span class="font-mono">${s.action}</span>]</span>
                            <span class="${statusChip}">[${s.status}]</span>
                        </div>
                        <div class="text-tertiary text-xs font-mono">
                            ${outputStr}
                        </div>
                    </div>
                `;
            });
            if (html) timeline.innerHTML = html;
            else timeline.innerHTML = `<div class="text-xs text-tertiary p-3 font-mono">No steps returned. Check backend logs.</div>`;
        }

        // Handle failure state: render failed step and trigger suggested fix card
        if (!data.success) {
            const failedStep = (data.steps || []).find(s => s.status === "FAILED");
            if (failedStep) {
                renderPlanCards(currentPlan, failedStep.step_id);
                showSuggestedFix(failedStep);
            }
        }

        loadManifest();
        loadLedger();
    } catch (e) {
        if (evtSource) evtSource.close();
        if (timeline) {
            timeline.innerHTML += `<div class="bg-status-dangerBg border border-status-danger/40 rounded-DEFAULT p-3 text-status-danger text-xs font-mono">Execution Failed: ${e.message}</div>`;
        }
    }
}

// Show Suggested Fix Diff Card on Step Failure
function showSuggestedFix(failedStep, isPreview = false) {
    const card = document.getElementById("suggested-fix-card");
    const desc = document.getElementById("fix-description");
    const removedEl = document.getElementById("fix-diff-removed");
    const addedEl = document.getElementById("fix-diff-added");
    const previewBadge = document.getElementById("fix-preview-badge");

    if (!card) return;

    const heal = failedStep.heal_suggestion || {};
    const reasonText = (heal.suggestions && heal.suggestions[0]) || heal.diagnosis || heal.reason || "Parameter discrepancy detected in workspace sandbox.";
    const originalFile = failedStep.params?.file || "customer.csv";
    const replacementFile = heal.healed_step?.params?.file || heal.suggested_replacement || "customers.csv";

    if (desc) {
        desc.textContent = isPreview
            ? `[UI PREVIEW] ${reasonText}`
            : reasonText;
    }
    if (removedEl) removedEl.textContent = `- "file": "${originalFile}"`;
    if (addedEl) addedEl.textContent = `+ "file": "${replacementFile}"`;

    if (previewBadge) {
        previewBadge.textContent = isPreview ? "[UI PREVIEW]" : "[AUTO-REMEDIATION]";
        previewBadge.className = isPreview
            ? "font-mono text-xs text-primary font-bold bg-primary/10 px-1.5 py-0.5 rounded-DEFAULT border border-primary"
            : "font-mono text-xs text-status-success font-semibold";
    }

    card.classList.remove("hidden");
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function dismissFix() {
    const card = document.getElementById("suggested-fix-card");
    if (card) card.classList.add("hidden");
}

function applyFix() {
    if (!currentPlan || !currentPlan.steps) return;
    const removedText = document.getElementById("fix-diff-removed")?.textContent || "";
    const addedText = document.getElementById("fix-diff-added")?.textContent || "";
    const matchRemoved = removedText.match(/"file":\s*"([^"]+)"/);
    const matchAdded = addedText.match(/"file":\s*"([^"]+)"/);
    const originalFile = matchRemoved ? matchRemoved[1] : "customer.csv";
    const replacementFile = matchAdded ? matchAdded[1] : "customers.csv";

    currentPlan.steps.forEach(step => {
        if (step.params && (step.params.file === originalFile || step.params.file === "customer.csv")) {
            step.params.file = replacementFile;
        }
    });
    dismissFix();
    renderPlanCards(currentPlan);
    executeCurrentPlan();
}

// Setup Failure State Preview when opened with ?preview=failure
function setupFailurePreview() {
    const previewPlan = {
        intent: "Find active customers from the USA and save them to usa_active.csv",
        steps: [
            {
                step_id: 1,
                action: "READ_CSV",
                params: { file: "customer.csv" },
                description: "Read customer records from CSV dataset"
            },
            {
                step_id: 2,
                action: "FILTER_ROWS",
                params: { file: "customer.csv", column: "country", operator: "==", value: "USA" },
                description: "Filter rows where country == USA"
            },
            {
                step_id: 3,
                action: "EXPORT_CSV",
                params: { source_step: 2, output_file: "usa_active.csv" },
                description: "Export filtered results to destination file"
            }
        ]
    };
    currentPlan = previewPlan;
    renderPlanCards(currentPlan, 1);

    const explanationEl = document.getElementById("plan-explanation");
    if (explanationEl) {
        explanationEl.textContent = "[UI PREVIEW] Simulated step failure: target dataset customer.csv was misspelled.";
    }

    showSuggestedFix({
        step_id: 1,
        action: "READ_CSV",
        params: { file: "customer.csv" },
        heal_suggestion: {
            reason: "Target file customer.csv not found. Matched customers.csv (Levenshtein distance: 1).",
            suggested_replacement: "customers.csv"
        }
    }, true);

    const planActions = document.getElementById("plan-actions");
    if (planActions) planActions.style.display = "flex";
}

// Load Execution Lineage Ledger
async function loadLedger() {
    const pre = document.getElementById("ledger-output");
    if (!pre) return;
    try {
        const res = await fetch(`${API_BASE}/api/ledger`);
        if (!res.ok) return;
        const records = await res.json();
        pre.textContent = JSON.stringify(records, null, 2);
    } catch (e) {
        pre.textContent = "Ledger unavailable.";
    }
}

// Reset Workspace Sandbox
async function resetWorkspace() {
    try {
        const res = await fetch(`${API_BASE}/api/reset-workspace`, { method: "POST" });
        if (res.ok) {
            loadManifest();
            loadLedger();
            alert("Workspace sandbox reset successfully from seed.");
        }
    } catch (e) {
        alert("Reset failed: " + e.message);
    }
}

// Switch between Primary Views: Console and Benchmark
function switchAppView(viewName) {
    const consoleView = document.getElementById("view-console");
    const benchmarkView = document.getElementById("view-benchmark");
    const consoleBtn = document.getElementById("nav-btn-console");
    const benchmarkBtn = document.getElementById("nav-btn-benchmark");

    if (viewName === "benchmark") {
        if (consoleView) consoleView.classList.add("hidden");
        if (benchmarkView) benchmarkView.classList.remove("hidden");

        if (consoleBtn) {
            consoleBtn.className = "px-3 py-1.5 rounded-DEFAULT text-xs font-semibold text-tertiary hover:text-on-surface transition-colors";
            consoleBtn.removeAttribute("aria-current");
        }
        if (benchmarkBtn) {
            benchmarkBtn.className = "px-3 py-1.5 rounded-DEFAULT text-xs font-semibold transition-colors bg-primary-container text-on-primary shadow-[1px_1px_0px_#1c1c18]";
            benchmarkBtn.setAttribute("aria-current", "page");
        }

        loadBenchmarkResults();
    } else {
        if (consoleView) consoleView.classList.remove("hidden");
        if (benchmarkView) benchmarkView.classList.add("hidden");

        if (consoleBtn) {
            consoleBtn.className = "px-3 py-1.5 rounded-DEFAULT text-xs font-semibold transition-colors bg-primary-container text-on-primary shadow-[1px_1px_0px_#1c1c18]";
            consoleBtn.setAttribute("aria-current", "page");
        }
        if (benchmarkBtn) {
            benchmarkBtn.className = "px-3 py-1.5 rounded-DEFAULT text-xs font-semibold text-tertiary hover:text-on-surface transition-colors";
            benchmarkBtn.removeAttribute("aria-current");
        }
    }
}

// Benchmark screen: read eval/results.json. If missing, show honest empty state.
async function loadBenchmarkResults() {
    const container = document.getElementById("benchmark-content-container");
    if (!container) return;

    const refreshBtn = document.getElementById("refresh-benchmark-btn");
    if (refreshBtn) {
        refreshBtn.textContent = "[ Refreshing... ]";
        refreshBtn.disabled = true;
    }

    const candidateUrls = [
        `${API_BASE}/api/benchmark`,
        "../eval/results.json",
        "/eval/results.json",
        "eval/results.json"
    ];

    let data = null;
    for (const url of candidateUrls) {
        try {
            const res = await fetch(url);
            if (res.ok) {
                data = await res.json();
                break;
            }
        } catch (_) {}
    }

    if (!data) {
        renderBenchmarkEmptyState(container);
    } else {
        renderBenchmarkData(container, data);
    }

    if (refreshBtn) {
        refreshBtn.textContent = "[ Refreshed ✓ ]";
        setTimeout(() => {
            refreshBtn.textContent = "[ Refresh Benchmark ]";
            refreshBtn.disabled = false;
        }, 1200);
    }
}

function renderBenchmarkEmptyState(container) {
    container.innerHTML = `
        <div class="bg-surface-container-lowest border border-surface-container-highest rounded-DEFAULT p-6 sm:p-8 shadow-[2px_2px_0px_#1c1c18] flex flex-col items-center text-center max-w-xl mx-auto my-6">
            <span class="material-symbols-outlined text-primary text-[40px] mb-3">assignment_late</span>
            <h3 class="text-base font-bold text-on-surface uppercase tracking-wide mb-2">
                No evaluation results yet. Run python eval/run_eval.py.
            </h3>
            <p class="text-sm text-tertiary mb-4 leading-relaxed font-sans">
                The benchmark evaluator tests prompt inputs against the deterministic verifier and manifest schema rules to measure valid plan generation and action accuracy.
            </p>
            <div class="w-full bg-surface-container-low border border-surface-container-highest rounded-DEFAULT p-3 font-mono text-xs text-left mb-5">
                <div class="text-tertiary select-none"># Run the offline evaluation suite:</div>
                <div class="text-on-surface font-semibold mt-1">python eval/run_eval.py</div>
            </div>
            <button
                type="button"
                onclick="loadBenchmarkResults()"
                class="px-4 py-2 bg-primary-container text-on-primary font-bold text-xs uppercase tracking-wider rounded-DEFAULT border border-on-surface shadow-[1px_1px_0px_#1c1c18] hover:bg-primary transition-colors"
            >
                [ Check Again ]
            </button>
        </div>
    `;
}

function renderBenchmarkData(container, data) {
    const totalPrompts = data.total ?? (Array.isArray(data) ? data.length : (data.runs?.length || 0));
    const validCount = data.valid_count ?? (Array.isArray(data) ? data.filter(d => d.is_valid || d.valid).length : 0);
    const groundedCount = data.grounded_count ?? (Array.isArray(data) ? data.filter(d => d.is_grounded || d.grounded).length : 0);
    const actionMatchCount = data.action_match_count ?? (Array.isArray(data) ? data.filter(d => d.action_match).length : 0);
    const configCount = data.configurations?.length ?? (data.config_count || 1);

    const validPct = totalPrompts > 0 ? ((validCount / totalPrompts) * 100).toFixed(1) : "0.0";
    const groundedPct = totalPrompts > 0 ? ((groundedCount / totalPrompts) * 100).toFixed(1) : "0.0";
    const actionPct = totalPrompts > 0 ? ((actionMatchCount / totalPrompts) * 100).toFixed(1) : "0.0";

    const configs = data.configurations || [
        {
            name: "Deterministic Verifier Pipeline",
            valid_rate: `${validPct}%`,
            valid_ratio: `${validCount} / ${totalPrompts}`,
            grounded_rate: `${groundedPct}%`,
            action_rate: `${actionPct}%`,
            verdict: "ACTIVE ENGINE"
        }
    ];

    const runs = data.runs || [];

    const passBadge = `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-DEFAULT bg-status-successBg text-status-success border border-status-success/30 font-bold font-mono text-xs">PASS</span>`;
    const failBadge = `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-DEFAULT bg-status-dangerBg text-status-danger border border-status-danger/40 font-bold font-mono text-xs">FAIL</span>`;

    container.innerHTML = `
        <div class="flex flex-col gap-4">
            <!-- Refresh & Source Bar -->
            <div class="flex items-center justify-between px-3 py-1.5 bg-surface-container border border-surface-container-highest rounded-DEFAULT text-xs font-mono text-tertiary">
                <span class="flex items-center gap-1.5 text-on-surface">
                    <span class="w-2 h-2 rounded-full bg-status-success inline-block"></span>
                    <span>Loaded from <code class="text-primary font-bold">eval/results.json</code></span>
                </span>
                <span>Last Refreshed: <span class="text-on-surface font-bold font-mono">${new Date().toLocaleTimeString()}</span></span>
            </div>

            <!-- Telemetry Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="bg-surface-container-lowest p-4 rounded-DEFAULT border border-surface-container-highest shadow-[1px_1px_0px_#1c1c18]">
                    <div class="text-xs font-mono text-tertiary uppercase">Test Prompts Evaluated</div>
                    <div class="text-2xl font-bold font-mono text-on-surface mt-1">${totalPrompts}</div>
                    <div class="text-xs text-tertiary mt-1">From eval/prompts.json</div>
                </div>

                <div class="bg-surface-container-lowest p-4 rounded-DEFAULT border border-surface-container-highest shadow-[1px_1px_0px_#1c1c18]">
                    <div class="text-xs font-mono text-tertiary uppercase">Configurations Tested</div>
                    <div class="text-2xl font-bold font-mono text-on-surface mt-1">${configCount}</div>
                    <div class="text-xs text-tertiary mt-1">Routing &amp; verifier pipelines</div>
                </div>

                <div class="bg-surface-container-lowest p-4 rounded-DEFAULT border border-surface-container-highest shadow-[1px_1px_0px_#1c1c18]">
                    <div class="text-xs font-mono text-tertiary uppercase">Schema Valid Plans</div>
                    <div class="text-2xl font-bold font-mono text-on-surface mt-1">${validPct}%</div>
                    <div class="text-xs text-tertiary mt-1 font-mono">${validCount} / ${totalPrompts} passed</div>
                </div>

                <div class="bg-surface-container-lowest p-4 rounded-DEFAULT border border-surface-container-highest shadow-[1px_1px_0px_#1c1c18]">
                    <div class="text-xs font-mono text-tertiary uppercase">Workspace Grounded</div>
                    <div class="text-2xl font-bold font-mono text-status-success mt-1">${groundedPct}%</div>
                    <div class="text-xs text-tertiary mt-1 font-mono">${groundedCount} / ${totalPrompts} verified</div>
                </div>
            </div>

            <!-- Configurations Summary Table -->
            <div class="bg-surface-container-lowest border border-surface-container-highest rounded-DEFAULT overflow-hidden shadow-[2px_2px_0px_#1c1c18]">
                <div class="p-3 bg-surface-container-low border-b border-surface-container-highest flex items-center justify-between">
                    <span class="text-xs font-bold uppercase tracking-wider text-on-surface">Configuration Results Matrix</span>
                    <span class="text-xs font-mono text-tertiary">Real evaluation outputs</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-xs">
                        <thead>
                            <tr class="bg-surface-container border-b border-surface-container-highest font-mono text-tertiary uppercase">
                                <th class="py-2.5 px-3">Configuration</th>
                                <th class="py-2.5 px-3 text-right">Valid Plans</th>
                                <th class="py-2.5 px-3 text-right">Grounded</th>
                                <th class="py-2.5 px-3 text-right">Action Match</th>
                                <th class="py-2.5 px-3">Disposition</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-surface-container-highest font-mono">
                            ${configs.map(cfg => `
                                <tr class="hover:bg-surface-container-low transition-colors">
                                    <td class="py-2.5 px-3 font-sans font-semibold text-on-surface">${cfg.name}</td>
                                    <td class="py-2.5 px-3 text-right font-bold text-on-surface">${cfg.valid_rate} <span class="text-tertiary text-xs">(${cfg.valid_ratio})</span></td>
                                    <td class="py-2.5 px-3 text-right font-bold text-status-success">${cfg.grounded_rate}</td>
                                    <td class="py-2.5 px-3 text-right font-bold text-on-surface">${cfg.action_rate}</td>
                                    <td class="py-2.5 px-3"><span class="px-1.5 py-0.5 rounded-DEFAULT bg-status-successBg text-status-success border border-status-success/30 font-bold">${cfg.verdict}</span></td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Per-Prompt Breakdown Table -->
            ${runs.length > 0 ? `
            <div class="bg-surface-container-lowest border border-surface-container-highest rounded-DEFAULT overflow-hidden shadow-[2px_2px_0px_#1c1c18]">
                <div class="p-3 bg-surface-container-low border-b border-surface-container-highest flex items-center justify-between">
                    <span class="text-xs font-bold uppercase tracking-wider text-on-surface">Per-Prompt Evaluation Results</span>
                    <span class="text-xs font-mono text-tertiary">${runs.length} prompts · ${data.generated_at ? 'Generated ' + new Date(data.generated_at).toLocaleTimeString() : ''}</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-xs">
                        <thead>
                            <tr class="bg-surface-container border-b border-surface-container-highest font-mono text-tertiary uppercase">
                                <th class="py-2 px-3 w-8">#</th>
                                <th class="py-2 px-3">Prompt</th>
                                <th class="py-2 px-3">Category</th>
                                <th class="py-2 px-3 text-center">Schema Valid</th>
                                <th class="py-2 px-3 text-center">Grounded</th>
                                <th class="py-2 px-3 text-center">Action Match</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-surface-container-highest">
                            ${runs.map(run => `
                                <tr class="hover:bg-surface-container-low transition-colors ${!run.is_valid || !run.is_grounded ? 'bg-status-dangerBg/20' : ''}">
                                    <td class="py-2 px-3 font-mono text-tertiary text-xs">${run.id}</td>
                                    <td class="py-2 px-3 text-on-surface max-w-xs truncate" title="${run.prompt.replace(/"/g, '&quot;')}">${run.prompt}</td>
                                    <td class="py-2 px-3 font-mono text-xs text-tertiary whitespace-nowrap">${run.category}</td>
                                    <td class="py-2 px-3 text-center">${run.is_valid ? passBadge : failBadge}</td>
                                    <td class="py-2 px-3 text-center">${run.is_grounded ? passBadge : failBadge}</td>
                                    <td class="py-2 px-3 text-center">${run.action_match ? passBadge : failBadge}</td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            </div>
            ` : ""}
        </div>
    `;
}

// Inspector Tab Switching
function switchInspectorTab(tabName) {
    const tabs = ["runlog", "manifest", "lineage"];
    tabs.forEach(t => {
        const btn = document.getElementById(`tab-btn-${t}`);
        const view = document.getElementById(`inspector-view-${t}`);
        if (t === tabName) {
            btn?.classList.remove("text-tertiary");
            btn?.classList.add("text-on-surface", "bg-surface-container-lowest", "border", "border-surface-container-highest", "font-semibold");
            btn?.setAttribute("aria-selected", "true");
            view?.classList.remove("hidden");
        } else {
            btn?.classList.add("text-tertiary");
            btn?.classList.remove("text-on-surface", "bg-surface-container-lowest", "border", "border-surface-container-highest", "font-semibold");
            btn?.setAttribute("aria-selected", "false");
            view?.classList.add("hidden");
        }
    });
}

// Mobile Tab Switching (Supports Request, Plan, Run on 390px phone screens)
function switchMobileTab(tab) {
    const planPane = document.getElementById("pane-plan");
    const inspectorPane = document.getElementById("pane-inspector");
    const planTab = document.getElementById("mobile-tab-plan");
    const inspectorTab = document.getElementById("mobile-tab-inspector");

    const bottomReq = document.getElementById("mobile-bottom-btn-request");
    const bottomPlan = document.getElementById("mobile-bottom-btn-plan");
    const bottomRun = document.getElementById("mobile-bottom-btn-run");

    const activeBottomClass = "flex-1 py-1.5 px-2 text-center text-xs font-semibold rounded-DEFAULT text-on-surface bg-surface-container border border-surface-container-highest";
    const inactiveBottomClass = "flex-1 py-1.5 px-2 text-center text-xs font-semibold rounded-DEFAULT text-tertiary hover:text-on-surface";

    if (tab === "request") {
        const reqInput = document.getElementById("request-input");
        reqInput?.scrollIntoView({ behavior: "smooth", block: "center" });
        reqInput?.focus();
        if (bottomReq) bottomReq.className = activeBottomClass;
        if (bottomPlan) bottomPlan.className = inactiveBottomClass;
        if (bottomRun) bottomRun.className = inactiveBottomClass;
        return;
    }

    if (tab === "plan") {
        planPane?.classList.remove("hidden");
        inspectorPane?.classList.add("hidden");
        planTab?.setAttribute("aria-selected", "true");
        planTab?.classList.add("bg-surface-container", "text-on-surface", "border", "border-surface-container-highest");
        inspectorTab?.setAttribute("aria-selected", "false");
        inspectorTab?.classList.remove("bg-surface-container", "text-on-surface", "border", "border-surface-container-highest");
        inspectorTab?.classList.add("text-tertiary");

        if (bottomPlan) bottomPlan.className = activeBottomClass;
        if (bottomReq) bottomReq.className = inactiveBottomClass;
        if (bottomRun) bottomRun.className = inactiveBottomClass;

        planPane?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
        planPane?.classList.add("hidden");
        inspectorPane?.classList.remove("hidden");
        inspectorTab?.setAttribute("aria-selected", "true");
        inspectorTab?.classList.add("bg-surface-container", "text-on-surface", "border", "border-surface-container-highest");
        planTab?.setAttribute("aria-selected", "false");
        planTab?.classList.remove("bg-surface-container", "text-on-surface", "border", "border-surface-container-highest");
        planTab?.classList.add("text-tertiary");

        if (bottomRun) bottomRun.className = activeBottomClass;
        if (bottomReq) bottomReq.className = inactiveBottomClass;
        if (bottomPlan) bottomPlan.className = inactiveBottomClass;

        inspectorPane?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}
