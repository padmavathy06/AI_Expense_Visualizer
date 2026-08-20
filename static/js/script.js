/**
 * AI Expense Visualizer - Ultra-Deep Interactive Engine
 * Guaranteed Universal AI Quick-Add, Real-Time Parsing, Hotkeys, and Theme Engine.
 */

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    ensureUniversalQuickAddModal();
    initModals();
    initAiQuickAdd();
    initInPageQuickAdd();
    initBulkSelection();
    initReceiptScanner();
    initAiChat();
    initGlobalHotkeys();
});

/* ==========================================================================
   1. THEME ENGINE
   ========================================================================== */

function initTheme() {
    const themeBtn = document.getElementById("themeToggleBtn");
    const savedTheme = localStorage.getItem("expense_theme") ||
        (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "dark"); // Default to sleek dark theme

    document.documentElement.setAttribute("data-theme", savedTheme);
    updateThemeIcon(savedTheme);

    if (themeBtn) {
        themeBtn.addEventListener("click", () => {
            const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
            const newTheme = currentTheme === "dark" ? "light" : "dark";

            document.documentElement.setAttribute("data-theme", newTheme);
            localStorage.setItem("expense_theme", newTheme);
            updateThemeIcon(newTheme);

            if (window.renderDashboardCharts) window.renderDashboardCharts();
            if (window.renderMonteCarloChart) window.renderMonteCarloChart();
            if (window.renderAnalyticsCharts) window.renderAnalyticsCharts();
        });
    }
}

function updateThemeIcon(theme) {
    const themeBtn = document.getElementById("themeToggleBtn");
    if (themeBtn) {
        themeBtn.innerHTML = theme === "dark" ? "☀️" : "🌙";
        themeBtn.setAttribute("title", `Switch to ${theme === "dark" ? "Light" : "Dark"} Mode`);
    }
}

/* ==========================================================================
   2. TOAST NOTIFICATIONS
   ========================================================================== */

function showToast(message, type = "success") {
    let container = document.getElementById("toastContainer");
    if (!container) {
        container = document.createElement("div");
        container.id = "toastContainer";
        container.className = "toast-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icon = type === "success" ? "✅" : (type === "error" ? "⚠️" : "ℹ️");
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        toast.style.transition = "all 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

/* ==========================================================================
   3. UNIVERSAL AI QUICK-ADD MODAL INJECTOR
   ========================================================================== */

function ensureUniversalQuickAddModal() {
    if (document.getElementById("quickAddModal")) return;

    const modalDiv = document.createElement("div");
    modalDiv.id = "quickAddModal";
    modalDiv.className = "modal-overlay";
    modalDiv.innerHTML = `
        <div class="modal-card">
            <div class="modal-header">
                <h3 style="font-weight: 800; display: flex; align-items: center; gap: 0.5rem;">
                    <span>⚡</span> AI Smart Quick-Add
                </h3>
                <button class="close-modal-btn">&times;</button>
            </div>
            <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1rem;">
                Type naturally (e.g. <em>"450 lunch via upi"</em>, <em>"coffee 120"</em>, <em>"swiggy 380"</em>). Press Enter to add!
            </p>
            <div class="form-control" style="margin-bottom: 1rem;">
                <input type="text" id="quickAddInput" class="form-input" placeholder="Type expense... e.g. 350 uber or 1200 wifi bill" autocomplete="off" autofocus>
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1.25rem;">
                <button type="button" class="btn btn-secondary btn-sm quick-chip">"450 lunch via UPI"</button>
                <button type="button" class="btn btn-secondary btn-sm quick-chip">"coffee 120"</button>
                <button type="button" class="btn btn-secondary btn-sm quick-chip">"swiggy 380"</button>
                <button type="button" class="btn btn-secondary btn-sm quick-chip">"1200 wifi bill"</button>
            </div>
            <div id="quickAddPreview" style="display: none; background: var(--bg-surface-subtle); padding: 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); margin-bottom: 1.25rem;"></div>
            <div style="display: flex; gap: 0.75rem;">
                <button type="button" id="quickAddSubmitBtn" class="btn btn-ai" style="width: 100%; padding: 0.75rem;">⚡ Confirm & Add Expense</button>
            </div>
        </div>
    `;
    document.body.appendChild(modalDiv);
}

/* ==========================================================================
   4. MODAL MANAGEMENT
   ========================================================================== */

function initModals() {
    document.addEventListener("click", (e) => {
        const trigger = e.target.closest("[data-modal-target]");
        if (trigger) {
            e.preventDefault();
            const targetId = trigger.getAttribute("data-modal-target");
            const modal = document.getElementById(targetId);
            if (modal) {
                modal.classList.add("active");
                const autoInput = modal.querySelector("input[autofocus], input[type='text'], input[type='number']");
                if (autoInput) setTimeout(() => autoInput.focus(), 50);
            }
        }

        const closer = e.target.closest(".close-modal-btn, [data-modal-close]");
        if (closer) {
            document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("active"));
        }

        if (e.target.classList.contains("modal-overlay")) {
            e.target.classList.remove("active");
        }
    });
}

/* ==========================================================================
   5. AI SMART QUICK-ADD (NLP CONTROLLER)
   ========================================================================== */

function initAiQuickAdd() {
    const input = document.getElementById("quickAddInput");
    const previewBox = document.getElementById("quickAddPreview");
    const submitBtn = document.getElementById("quickAddSubmitBtn");

    if (!input || !submitBtn) return;

    let debounceTimer = null;

    // Real-time live parsing as user types
    input.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            const text = input.value.trim();
            if (!text) {
                if (previewBox) previewBox.style.display = "none";
                return;
            }

            try {
                const res = await fetch("/api/ai/quick-parse", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text })
                });
                const data = await res.json();

                if (data && data.amount > 0 && previewBox) {
                    previewBox.style.display = "block";
                    previewBox.innerHTML = `
                        <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.35rem; font-weight: 600;">DETECTED PARAMETERS:</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center;">
                            <span class="badge-category cat-${data.category}">🏷️ ${data.category}</span>
                            <span class="badge-payment">💳 ${data.payment_method}</span>
                            <span class="badge-payment">📅 ${data.expense_date}</span>
                            <span style="font-weight: 800; font-family: 'JetBrains Mono'; font-size: 1.1rem; color: var(--text-primary);">₹${Number(data.amount).toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
                        </div>
                    `;
                }
            } catch (e) {
                // Ignore silent preview failure
            }
        }, 300);
    });

    // Suggestion chips
    document.addEventListener("click", (e) => {
        const chip = e.target.closest(".quick-chip");
        if (chip) {
            input.value = chip.textContent.replace(/^"|"$/g, "").trim();
            input.dispatchEvent(new Event("input"));
            input.focus();
        }
    });

    async function submitQuickExpense() {
        const text = input.value.trim();
        if (!text) {
            showToast("Please enter an expense phrase (e.g. '450 lunch')", "error");
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = "⚡ Adding Expense...";

        try {
            const res = await fetch("/api/ai/quick-add", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text })
            });
            const result = await res.json();

            if (result && result.success) {
                showToast(`Logged ₹${result.expense.amount} for ${result.expense.category}!`, "success");
                input.value = "";
                if (previewBox) previewBox.style.display = "none";
                document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("active"));
                setTimeout(() => window.location.reload(), 600);
            } else {
                showToast(result.error || "Could not identify an expense amount in your text.", "error");
            }
        } catch (err) {
            showToast("Error processing expense. Please try again.", "error");
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = "⚡ Confirm & Add Expense";
        }
    }

    submitBtn.addEventListener("click", submitQuickExpense);

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            submitQuickExpense();
        }
    });
}

/* ==========================================================================
   6. GLOBAL SHORTCUTS
   ========================================================================== */

function initGlobalHotkeys() {
    document.addEventListener("keydown", (e) => {
        // Ctrl+K or Cmd+K opens AI Quick Add
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            const modal = document.getElementById("quickAddModal");
            if (modal) {
                modal.classList.add("active");
                const input = document.getElementById("quickAddInput");
                if (input) setTimeout(() => input.focus(), 50);
            }
        }
        // Escape closes any open modal
        if (e.key === "Escape") {
            document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("active"));
        }
    });
}

/* ==========================================================================
   7. RECEIPT SCANNER & OCR
   ========================================================================== */

function initReceiptScanner() {
    const fileInput = document.getElementById("receiptFileInput");
    const dropZone = document.getElementById("receiptDropZone");
    const resultBox = document.getElementById("receiptScanResult");
    const statusText = document.getElementById("receiptScanStatus");

    if (!fileInput || !dropZone) return;

    dropZone.addEventListener("click", () => fileInput.click());

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.style.borderColor = "var(--brand-primary)";
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.style.borderColor = "var(--border-strong)";
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.style.borderColor = "var(--border-strong)";
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleReceiptUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            handleReceiptUpload(fileInput.files[0]);
        }
    });

    async function handleReceiptUpload(file) {
        if (statusText) {
            statusText.style.display = "block";
            statusText.textContent = `🔍 Scanning "${file.name}" with AI Vision...`;
        }

        const formData = new FormData();
        formData.append("receipt", file);

        try {
            const res = await fetch("/api/ai/scan-receipt", {
                method: "POST",
                body: formData
            });
            const data = await res.json();

            if (data && data.success) {
                if (statusText) statusText.style.display = "none";
                if (resultBox) {
                    resultBox.style.display = "block";
                    resultBox.innerHTML = `
                        <div style="background: var(--bg-surface-subtle); padding: 1.25rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
                            <h4 style="font-weight: 700; margin-bottom: 0.5rem;">🧾 ${data.merchant || "Extracted Receipt"}</h4>
                            <p style="font-size: 0.9rem; margin-bottom: 0.4rem;"><strong>Amount:</strong> ₹${Number(data.amount).toFixed(2)}</p>
                            <p style="font-size: 0.9rem; margin-bottom: 0.4rem;"><strong>Category:</strong> <span class="badge-category cat-${data.category}">${data.category}</span></p>
                            <p style="font-size: 0.9rem; margin-bottom: 0.4rem;"><strong>Date:</strong> ${data.expense_date}</p>
                            <p style="font-size: 0.9rem; margin-bottom: 0.75rem;"><strong>Payment Method:</strong> ${data.payment_method}</p>
                            <button id="saveReceiptExpenseBtn" class="btn btn-primary btn-sm" style="width: 100%;">Save to Expenses</button>
                        </div>
                    `;

                    document.getElementById("saveReceiptExpenseBtn").addEventListener("click", async () => {
                        const quickAddRes = await fetch("/api/ai/quick-add", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                text: `Spent ${data.amount} on ${data.category} at ${data.merchant} using ${data.payment_method} on ${data.expense_date}`
                            })
                        });
                        const qData = await quickAddRes.json();
                        if (qData.success) {
                            showToast("Receipt expense saved!", "success");
                            setTimeout(() => window.location.reload(), 700);
                        }
                    });
                }
            } else {
                if (statusText) statusText.textContent = "⚠️ Could not scan receipt.";
            }
        } catch (err) {
            console.error("Receipt upload error:", err);
            if (statusText) statusText.textContent = "⚠️ Error uploading receipt.";
        }
    }
}

/* ==========================================================================
   8. MULTI-PERSONA AI FINANCIAL ADVISOR
   ========================================================================== */

function initAiChat() {
    const chatInput = document.getElementById("aiChatInput");
    const sendBtn = document.getElementById("aiChatSendBtn");
    const messagesContainer = document.getElementById("aiChatMessages");

    if (!chatInput || !sendBtn || !messagesContainer) return;

    let selectedPersona = "Finley";
    let chatHistory = [];

    document.querySelectorAll(".persona-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            document.querySelectorAll(".persona-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            selectedPersona = chip.getAttribute("data-persona");
            appendMessage(`*Switched advisor persona to **${selectedPersona}***.`, "ai");
        });
    });

    document.querySelectorAll(".ai-prompt-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            chatInput.value = chip.textContent.trim();
            sendMessage();
        });
    });

    async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;

        appendMessage(message, "user");
        chatInput.value = "";

        const typingId = "typing-" + Date.now();
        const typingElem = document.createElement("div");
        typingElem.id = typingId;
        typingElem.className = "chat-bubble bubble-ai";
        typingElem.innerHTML = `<em>${selectedPersona} is analyzing your finances...</em>`;
        messagesContainer.appendChild(typingElem);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        try {
            const res = await fetch("/api/ai/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message, history: chatHistory, persona: selectedPersona })
            });
            const data = await res.json();

            typingElem.remove();
            appendMessage(data.reply || "I analyzed your numbers. How else can I help?", "ai");
            chatHistory.push({ role: "user", content: message });
            chatHistory.push({ role: "assistant", content: data.reply });
        } catch (err) {
            typingElem.remove();
            appendMessage("⚠️ Connection error. Please try again.", "ai");
        }
    }

    function appendMessage(text, sender) {
        const bubble = document.createElement("div");
        bubble.className = `chat-bubble bubble-${sender}`;
        let formatted = text
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.*?)\*/g, "<em>$1</em>")
            .replace(/\n/g, "<br>");
        bubble.innerHTML = formatted;
        messagesContainer.appendChild(bubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    sendBtn.addEventListener("click", sendMessage);
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            sendMessage();
        }
    });
}

/* ==========================================================================
   9. IN-PAGE INSTANT QUICK-ADD
   ========================================================================== */

function initInPageQuickAdd() {
    const input = document.getElementById("inPageQuickInput");
    const btn = document.getElementById("inPageQuickBtn");
    const preview = document.getElementById("inPageQuickPreview");

    if (!input || !btn) return;

    let debounceTimer = null;

    input.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            const text = input.value.trim();
            if (!text) {
                if (preview) preview.style.display = "none";
                return;
            }

            try {
                const res = await fetch("/api/ai/quick-parse", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text })
                });
                const data = await res.json();
                if (data && data.amount > 0 && preview) {
                    preview.style.display = "block";
                    preview.innerHTML = `
                        ✨ <strong>Detected:</strong> ₹${data.amount.toFixed(2)} &bull;
                        <span class="badge-category cat-${data.category}">${data.category}</span> &bull;
                        <span>${data.payment_method}</span> &bull;
                        <span>${data.description}</span>
                    `;
                }
            } catch (e) {}
        }, 250);
    });

    async function handleInPageSubmit() {
        const text = input.value.trim();
        if (!text) {
            showToast("Type an expense first (e.g. '450 lunch')", "error");
            return;
        }

        btn.disabled = true;
        btn.textContent = "+ Adding...";

        try {
            const res = await fetch("/api/ai/quick-add", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text })
            });
            const result = await res.json();

            if (result && result.success) {
                showToast(`Logged ₹${result.expense.amount} for ${result.expense.category}!`, "success");
                input.value = "";
                if (preview) preview.style.display = "none";
                setTimeout(() => window.location.reload(), 500);
            } else {
                showToast(result.error || "Could not extract expense amount.", "error");
            }
        } catch (e) {
            showToast("Error logging expense.", "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "+ Add";
        }
    }

    btn.addEventListener("click", handleInPageSubmit);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            handleInPageSubmit();
        }
    });
}

/* ==========================================================================
   10. BULK CHECKBOX SELECTION
   ========================================================================== */

function initBulkSelection() {
    const selectAll = document.getElementById("selectAllCheckbox");
    const rowCheckboxes = document.querySelectorAll(".row-checkbox");
    const bulkBar = document.getElementById("bulkActionBar");
    const countText = document.getElementById("selectedCountText");

    if (!selectAll || rowCheckboxes.length === 0) return;

    function updateBulkBar() {
        const checkedBoxes = document.querySelectorAll(".row-checkbox:checked");
        const count = checkedBoxes.length;

        if (bulkBar && countText) {
            if (count > 0) {
                bulkBar.style.display = "flex";
                countText.textContent = `${count} expense${count > 1 ? 's' : ''} selected`;
            } else {
                bulkBar.style.display = "none";
            }
        }

        selectAll.checked = (count === rowCheckboxes.length && count > 0);
        selectAll.indeterminate = (count > 0 && count < rowCheckboxes.length);
    }

    selectAll.addEventListener("change", () => {
        rowCheckboxes.forEach(cb => {
            cb.checked = selectAll.checked;
        });
        updateBulkBar();
    });

    rowCheckboxes.forEach(cb => {
        cb.addEventListener("change", updateBulkBar);
    });
}

