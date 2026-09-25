// ==============================================================================
// State & Variables
// ==============================================================================
let conversationHistory = [];
let isGenerating = false;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    // Configure marked options if available
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            highlight: function(code, lang) {
                if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                    return hljs.highlight(code, { language: lang }).value;
                }
                return code;
            },
            breaks: true,
            gfm: true
        });
    }
});

// ==============================================================================
// Tab switching for integration code snippets
// ==============================================================================
function switchTab(tabName) {
    document.querySelectorAll('.snippet-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('text-blue-400', 'bg-slate-800');
        btn.classList.add('text-slate-400');
    });

    const activeSnippet = document.getElementById(`snippet-${tabName}`);
    const activeTabBtn = document.getElementById(`tab-${tabName}`);

    if (activeSnippet) activeSnippet.classList.remove('hidden');
    if (activeTabBtn) {
        activeTabBtn.classList.remove('text-slate-400');
        activeTabBtn.classList.add('text-blue-400', 'bg-slate-800');
    }
}

// Copy to clipboard helper
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy: ', err);
    });
}

function copyActiveSnippet() {
    const active = document.querySelector('.snippet-content:not(.hidden) code');
    if (active) {
        copyToClipboard(active.innerText);
    }
}

function toggleKeyVisibility(keyId) {
    const input = document.getElementById(`key-input-${keyId}`);
    const icon = document.getElementById(`eye-icon-${keyId}`);
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// Toast notification
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-5 right-5 bg-blue-600 text-white px-4 py-2.5 rounded-xl shadow-2xl text-xs font-semibold z-50 flex items-center space-x-2 transition-all transform duration-300';
    toast.innerHTML = `<i class="fa-solid fa-check"></i> <span>${message}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

// Generate new API Key
async function generateNewKey() {
    const name = prompt("Enter a label for this API key:", "Secondary Key");
    if (!name) return;

    try {
        const res = await fetch('/api/user/keys', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name})
        });
        if (res.ok) {
            showToast('API key generated successfully!');
            setTimeout(() => window.location.reload(), 600);
        } else {
            alert('Failed to generate key');
        }
    } catch (e) {
        console.error(e);
        alert('Network error while generating key');
    }
}

// ==============================================================================
// Interactive Qwen 2.5 3B Chat Component
// ==============================================================================
function toggleChatSettings() {
    const drawer = document.getElementById('chat-settings-drawer');
    const btn = document.getElementById('chat-settings-btn');
    if (drawer) {
        drawer.classList.toggle('hidden');
        if (!drawer.classList.contains('hidden')) {
            btn.classList.add('bg-slate-700', 'text-white');
        } else {
            btn.classList.remove('bg-slate-700', 'text-white');
        }
    }
}

function clearChatHistory() {
    conversationHistory = [];
    const container = document.getElementById('chat-messages-container');
    if (container) {
        container.innerHTML = `
            <div class="flex items-start space-x-3 chat-message assistant-message">
                <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-sky-500 flex items-center justify-center text-white flex-shrink-0 text-xs shadow-md shadow-blue-600/30">
                    <i class="fa-solid fa-robot"></i>
                </div>
                <div class="flex-1 space-y-1">
                    <div class="flex items-center space-x-2">
                        <span class="text-xs font-semibold text-blue-400">Qwen 2.5 3B</span>
                        <span class="text-[10px] text-slate-500">AI Assistant</span>
                    </div>
                    <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl rounded-tl-sm text-sm text-slate-200 leading-relaxed max-w-[90%] shadow-md">
                        Conversation cleared. How can I assist you next?
                    </div>
                </div>
            </div>
        `;
    }
    showToast('Conversation cleared.');
}

function useQuickPrompt(text) {
    const input = document.getElementById('chat-input');
    if (input) {
        input.value = text;
        input.focus();
        handleChatSubmit(new Event('submit'));
    }
}

function handleChatKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        handleChatSubmit(event);
    }
}

function formatContent(text) {
    if (typeof marked !== 'undefined') {
        try {
            return marked.parse(text);
        } catch (e) {
            console.error(e);
        }
    }
    // Fallback: Escape HTML
    const div = document.createElement('div');
    div.innerText = text;
    return div.innerHTML.replace(/\n/g, '<br>');
}

function appendUserMessage(text) {
    const container = document.getElementById('chat-messages-container');
    const msgId = 'msg-' + Date.now();
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const msgHtml = `
        <div class="flex items-start justify-end space-x-3 chat-message user-message" id="${msgId}">
            <div class="flex-1 flex flex-col items-end space-y-1">
                <div class="flex items-center space-x-2">
                    <span class="text-[10px] text-slate-500">${timeStr}</span>
                    <span class="text-xs font-semibold text-slate-300">You</span>
                </div>
                <div class="p-3.5 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-2xl rounded-tr-sm text-sm leading-relaxed max-w-[85%] shadow-md break-words">
                    ${formatContent(text)}
                </div>
            </div>
            <div class="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 flex-shrink-0 text-xs shadow-md">
                <i class="fa-solid fa-user"></i>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', msgHtml);
    container.scrollTop = container.scrollHeight;
}

function appendAssistantPlaceholder() {
    const container = document.getElementById('chat-messages-container');
    const msgId = 'placeholder-' + Date.now();

    const placeholderHtml = `
        <div class="flex items-start space-x-3 chat-message assistant-message" id="${msgId}">
            <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-sky-500 flex items-center justify-center text-white flex-shrink-0 text-xs shadow-md shadow-blue-600/30">
                <i class="fa-solid fa-robot"></i>
            </div>
            <div class="flex-1 space-y-1">
                <div class="flex items-center space-x-2">
                    <span class="text-xs font-semibold text-blue-400">Qwen 2.5 3B</span>
                    <span class="text-[10px] text-amber-400 flex items-center"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Thinking...</span>
                </div>
                <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl rounded-tl-sm text-sm text-slate-400 leading-relaxed max-w-[90%] shadow-md flex items-center space-x-2">
                    <span class="inline-block w-2 h-2 rounded-full bg-blue-500 animate-ping"></span>
                    <span>Generating response from cluster...</span>
                </div>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', placeholderHtml);
    container.scrollTop = container.scrollHeight;
    return msgId;
}

function updateAssistantMessage(placeholderId, content, usage) {
    const placeholder = document.getElementById(placeholderId);
    if (!placeholder) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const formattedHtml = formatContent(content);
    const tokenInfo = usage && usage.total_tokens ? `${usage.total_tokens} tokens` : '';

    placeholder.outerHTML = `
        <div class="flex items-start space-x-3 chat-message assistant-message group">
            <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-sky-500 flex items-center justify-center text-white flex-shrink-0 text-xs shadow-md shadow-blue-600/30">
                <i class="fa-solid fa-robot"></i>
            </div>
            <div class="flex-1 space-y-1">
                <div class="flex items-center justify-between max-w-[90%]">
                    <div class="flex items-center space-x-2">
                        <span class="text-xs font-semibold text-blue-400">Qwen 2.5 3B</span>
                        <span class="text-[10px] text-slate-500">${timeStr}</span>
                    </div>
                    ${tokenInfo ? `<span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-blue-300 font-mono"><i class="fa-solid fa-bolt text-amber-400 mr-1"></i>${tokenInfo}</span>` : ''}
                </div>
                <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl rounded-tl-sm text-sm text-slate-200 leading-relaxed max-w-[90%] shadow-md prose prose-invert prose-sm break-words">
                    ${formattedHtml}
                </div>
                <div class="opacity-0 group-hover:opacity-100 transition flex items-center space-x-2 pt-1">
                    <button onclick="copyToClipboard(\`${content.replace(/`/g, '\\`').replace(/\\/g, '\\\\')}\`)" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-md text-[10px] transition flex items-center space-x-1">
                        <i class="fa-solid fa-copy"></i>
                        <span>Copy message</span>
                    </button>
                </div>
            </div>
        </div>
    `;

    const container = document.getElementById('chat-messages-container');
    container.scrollTop = container.scrollHeight;
}
                </div>
            </div>
        </div>
    `;

    const container = document.getElementById('chat-messages-container');
    container.scrollTop = container.scrollHeight;
}

function updateAssistantError(placeholderId, errorMsg) {
    const placeholder = document.getElementById(placeholderId);
    if (!placeholder) return;

    placeholder.outerHTML = `
        <div class="flex items-start space-x-3 chat-message assistant-message">
            <div class="w-8 h-8 rounded-xl bg-red-600/20 border border-red-500/30 flex items-center justify-center text-red-400 flex-shrink-0 text-xs shadow-md">
                <i class="fa-solid fa-circle-exclamation"></i>
            </div>
            <div class="flex-1 space-y-1">
                <div class="flex items-center space-x-2">
                    <span class="text-xs font-semibold text-red-400">Error</span>
                </div>
                <div class="p-4 bg-red-950/40 border border-red-800/60 rounded-2xl rounded-tl-sm text-sm text-red-300 leading-relaxed max-w-[90%] shadow-md">
                    ${errorMsg}
                </div>
            </div>
        </div>
    `;
    const container = document.getElementById('chat-messages-container');
    container.scrollTop = container.scrollHeight;
}

async function handleChatSubmit(event) {
    if (event) event.preventDefault();
    if (isGenerating) return;

    const input = document.getElementById('chat-input');
    const promptText = input.value.trim();
    if (!promptText) return;

    const sendBtn = document.getElementById('chat-send-btn');
    const statusIndicator = document.getElementById('chat-status-indicator');
    const systemPrompt = document.getElementById('chat-system-prompt')?.value || 'You are a helpful, expert AI assistant powered by Qwen 2.5 3B.';
    const temperature = parseFloat(document.getElementById('chat-temperature')?.value || '0.7');
    const maxTokens = parseInt(document.getElementById('chat-max-tokens')?.value || '1024');

    // Append to UI & Clear input
    appendUserMessage(promptText);
    input.value = '';
    input.style.height = 'auto';

    // Build payload messages
    const messages = [];
    if (systemPrompt) {
        messages.push({ role: 'system', content: systemPrompt });
    }
    // Include full conversation history for multi-turn context
    conversationHistory.forEach(m => messages.push(m));
    messages.push({ role: 'user', content: promptText });

    // Show assistant placeholder
    const placeholderId = appendAssistantPlaceholder();

    // Lock UI state
    isGenerating = true;
    sendBtn.disabled = true;
    statusIndicator.innerHTML = '<span class="text-amber-400"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Processing...</span>';

    try {
        const response = await fetch('/api/user/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: 'qwen2.5:3b',
                messages: messages,
                temperature: temperature,
                max_tokens: maxTokens,
                stream: false
            })
        });

        if (!response.ok) {
            const errData = await response.json();
            const msg = errData.detail?.error?.message || errData.detail || 'Inference error';
            updateAssistantError(placeholderId, msg);
            statusIndicator.innerHTML = '<span class="text-red-400">Failed</span>';
            return;
        }

        const data = await response.json();
        const replyContent = data.choices && data.choices[0] && data.choices[0].message
            ? data.choices[0].message.content
            : 'No response content.';
        const usage = data.usage || { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };

        // Save into local conversation history
        conversationHistory.push({ role: 'user', content: promptText });
        conversationHistory.push({ role: 'assistant', content: replyContent });

        // Update UI
        updateAssistantMessage(placeholderId, replyContent, usage);
        statusIndicator.innerHTML = '<span class="text-emerald-400">Ready</span>';

        // Update Token Balance across the dashboard
        updateRemainingBalance();

        // Append to Recent Usage History table live
        appendUsageLogRow('qwen2.5:3b', usage.prompt_tokens, usage.completion_tokens, usage.total_tokens);

    } catch (err) {
        console.error(err);
        updateAssistantError(placeholderId, `Network error: ${err.message}`);
        statusIndicator.innerHTML = '<span class="text-red-400">Network Error</span>';
    } finally {
        isGenerating = false;
        sendBtn.disabled = false;
        input.focus();
    }
}

// Live update of balance card and progress bar
async function updateRemainingBalance() {
    try {
        const res = await fetch('/api/user/me');
        if (res.ok) {
            const data = await res.json();
            const counter = document.getElementById('balance-counter');
            if (counter) {
                counter.innerHTML = `${data.remaining_tokens.toLocaleString()} <span class="text-base font-normal text-blue-400">tokens</span>`;
            }

            const quotaText = document.getElementById('quota-usage-text');
            const progressBar = document.getElementById('balance-progress-bar');
            const totalConsumed = document.getElementById('total-consumed-stat');

            if (data.monthly_quota && data.monthly_quota > 0) {
                const pct = Math.min(100, Math.round((data.remaining_tokens / data.monthly_quota) * 100));
                if (quotaText) {
                    quotaText.innerText = `${data.remaining_tokens.toLocaleString()} / ${data.monthly_quota.toLocaleString()} tokens (${pct}%)`;
                }
                if (progressBar) {
                    progressBar.style.width = `${pct}%`;
                }
            }
            if (totalConsumed) {
                totalConsumed.innerText = `${data.total_consumed.toLocaleString()} tokens`;
            }
        }
    } catch (e) {
        console.error(e);
    }
}

function appendUsageLogRow(model, promptTokens, completionTokens, totalTokens) {
    const tbody = document.getElementById('usage-logs-tbody');
    if (!tbody) return;

    // Remove empty placeholder row if exists
    if (tbody.innerText.includes('No usage records yet')) {
        tbody.innerHTML = '';
    }

    const now = new Date();
    const timeFormatted = now.getFullYear() + '-' +
        String(now.getMonth() + 1).padStart(2, '0') + '-' +
        String(now.getDate()).padStart(2, '0') + ' ' +
        String(now.getHours()).padStart(2, '0') + ':' +
        String(now.getMinutes()).padStart(2, '0') + ':' +
        String(now.getSeconds()).padStart(2, '0');

    const rowHtml = `
        <tr class="hover:bg-slate-850/50 transition">
            <td class="px-4 py-2.5 font-mono text-slate-400">${timeFormatted}</td>
            <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded bg-slate-800 text-blue-300 font-mono">${model}</span></td>
            <td class="px-4 py-2.5">${promptTokens}</td>
            <td class="px-4 py-2.5">${completionTokens}</td>
            <td class="px-4 py-2.5 font-bold text-blue-400">${totalTokens}</td>
            <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 text-[10px] font-semibold">200 OK</span></td>
        </tr>
    `;
    tbody.insertAdjacentHTML('afterbegin', rowHtml);
}

// ==============================================================================
// Admin Modal Handlers
// ==============================================================================
function openAddTokensModal(userId, username) {
    document.getElementById('modal-user-id').value = userId;
    document.getElementById('modal-username').innerText = username;
    document.getElementById('addTokensModal').classList.remove('hidden');
}

function closeAddTokensModal() {
    document.getElementById('addTokensModal').classList.add('hidden');
}

async function submitAddTokens() {
    const userId = parseInt(document.getElementById('modal-user-id').value);
    const amount = parseInt(document.getElementById('modal-token-amount').value);

    if (!amount || amount <= 0) {
        alert('Please enter a positive token amount.');
        return;
    }

    try {
        const res = await fetch('/api/admin/tokens/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId, amount: amount})
        });

        if (res.ok) {
            const data = await res.json();
            closeAddTokensModal();
            showToast(data.message);
            const balSpan = document.getElementById(`user-balance-${userId}`);
            if (balSpan) balSpan.innerText = data.new_balance.toLocaleString();
        } else {
            alert('Failed to grant tokens.');
        }
    } catch (e) {
        alert('Network error.');
    }
}

function openSetQuotaModal() {
    document.getElementById('setQuotaModal').classList.remove('hidden');
}

function closeSetQuotaModal() {
    document.getElementById('setQuotaModal').classList.add('hidden');
}

async function submitSetQuota() {
    const quota = parseInt(document.getElementById('modal-quota-amount').value);
    const applyExisting = document.getElementById('modal-apply-existing').checked;

    if (!quota || quota <= 0) {
        alert('Please enter a valid quota.');
        return;
    }

    try {
        const res = await fetch('/api/admin/quota/set', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({quota: quota, apply_to_existing_users: applyExisting})
        });

        if (res.ok) {
            const data = await res.json();
            closeSetQuotaModal();
            showToast(data.message);
            setTimeout(() => window.location.reload(), 600);
        } else {
            alert('Failed to set monthly quota.');
        }
    } catch (e) {
        alert('Network error.');
    }
}

async function resetAllBalances() {
    if (!confirm('Are you sure you want to reset all user balances to their monthly quota?')) {
        return;
    }

    try {
        const res = await fetch('/api/admin/balances/reset', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({reset_to_quota: true})
        });

        if (res.ok) {
            const data = await res.json();
            showToast(data.message);
            setTimeout(() => window.location.reload(), 600);
        } else {
            alert('Failed to reset balances.');
        }
    } catch (e) {
        alert('Network error.');
    }
}
