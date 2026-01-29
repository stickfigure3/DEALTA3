/**
 * DELTA3 - AI Coding Assistant
 * Frontend Application
 */

// === Configuration ===
const API_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000' 
    : 'https://api.delta3.ai'; // Update with your API Gateway URL

// === State ===
let sessionToken = localStorage.getItem('sessionToken');
let currentUser = null;

// === DOM Elements ===
const screens = {
    auth: document.getElementById('auth-screen'),
    setup: document.getElementById('setup-screen'),
    chat: document.getElementById('chat-screen')
};

// === Utilities ===
function showScreen(name) {
    Object.values(screens).forEach(s => s.classList.remove('active'));
    screens[name].classList.add('active');
}

function showError(elementId, message) {
    const el = document.getElementById(elementId);
    if (el) {
        el.textContent = message;
        setTimeout(() => el.textContent = '', 5000);
    }
}

async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (sessionToken) {
        headers['X-Session-Token'] = sessionToken;
    }
    
    const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.error || 'Request failed');
    }
    
    return data;
}

// === Auth ===
async function checkAuth() {
    if (!sessionToken) {
        showScreen('auth');
        return;
    }
    
    try {
        const user = await apiRequest('/auth/me');
        currentUser = user;
        
        if (!user.gemini_key_set) {
            showScreen('setup');
        } else {
            showScreen('chat');
            loadChatHistory();
        }
    } catch (e) {
        localStorage.removeItem('sessionToken');
        sessionToken = null;
        showScreen('auth');
    }
}

// Auth tabs
document.querySelectorAll('.auth-tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.auth-tabs .tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
        
        tab.classList.add('active');
        document.getElementById(`${tab.dataset.tab}-form`).classList.add('active');
    });
});

// Login form
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    
    try {
        const result = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });
        
        sessionToken = result.session_token;
        localStorage.setItem('sessionToken', sessionToken);
        currentUser = result;
        
        if (!result.gemini_key_set) {
            showScreen('setup');
        } else {
            showScreen('chat');
            loadChatHistory();
        }
    } catch (e) {
        showError('login-error', e.message);
    }
});

// Register form
document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const confirm = document.getElementById('register-confirm').value;
    
    if (password !== confirm) {
        showError('register-error', 'Passwords do not match');
        return;
    }
    
    try {
        await apiRequest('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });
        
        // Auto-login after registration
        const result = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });
        
        sessionToken = result.session_token;
        localStorage.setItem('sessionToken', sessionToken);
        currentUser = result;
        
        showScreen('setup');
    } catch (e) {
        showError('register-error', e.message);
    }
});

// Setup form (Gemini API key)
document.getElementById('setup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const geminiKey = document.getElementById('gemini-key').value;
    
    try {
        await apiRequest('/auth/gemini-key', {
            method: 'POST',
            body: JSON.stringify({ gemini_key: geminiKey })
        });
        
        showScreen('chat');
        loadChatHistory();
    } catch (e) {
        showError('setup-error', e.message);
    }
});

// Logout buttons
document.getElementById('logout-setup').addEventListener('click', logout);
document.getElementById('logout-btn').addEventListener('click', logout);

function logout() {
    localStorage.removeItem('sessionToken');
    sessionToken = null;
    currentUser = null;
    showScreen('auth');
}

// === Chat ===
const messagesContainer = document.getElementById('messages');
const messageInput = document.getElementById('message-input');
const chatForm = document.getElementById('chat-form');
const sendBtn = document.getElementById('send-btn');

// Auto-resize textarea
messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
});

// Handle Enter key
messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

// Send message
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const message = messageInput.value.trim();
    if (!message) return;
    
    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    // Remove welcome message
    const welcome = messagesContainer.querySelector('.welcome-message');
    if (welcome) welcome.remove();
    
    // Add user message
    addMessage('user', message);
    
    // Disable input
    sendBtn.disabled = true;
    
    // Add loading indicator
    const loadingEl = document.createElement('div');
    loadingEl.className = 'message assistant';
    loadingEl.innerHTML = '<div class="message-content loading">Thinking</div>';
    messagesContainer.appendChild(loadingEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    try {
        const result = await apiRequest('/chat/send', {
            method: 'POST',
            body: JSON.stringify({ message })
        });
        
        // Remove loading
        loadingEl.remove();
        
        // Add response
        addMessage('assistant', result.response, result.tool_calls);
    } catch (e) {
        loadingEl.remove();
        addMessage('assistant', `Error: ${e.message}`);
    }
    
    sendBtn.disabled = false;
});

function addMessage(role, content, toolCalls = []) {
    const el = document.createElement('div');
    el.className = `message ${role}`;
    
    // Format content (basic markdown)
    let html = formatContent(content);
    
    // Add tool calls if any
    if (toolCalls && toolCalls.length > 0) {
        html += '<div class="tool-calls">';
        toolCalls.forEach(tc => {
            html += `<div class="tool-call"><span class="icon">✓</span> ${tc.tool}</div>`;
        });
        html += '</div>';
    }
    
    el.innerHTML = `<div class="message-content">${html}</div>`;
    messagesContainer.appendChild(el);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function formatContent(text) {
    // Escape HTML
    text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Code blocks
    text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
        return `<pre><code>${code.trim()}</code></pre>`;
    });
    
    // Inline code
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Bold
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Line breaks
    text = text.replace(/\n/g, '<br>');
    
    return text;
}

async function loadChatHistory() {
    try {
        const data = await apiRequest('/chat/history?limit=50');
        
        if (data.history && data.history.length > 0) {
            // Remove welcome message
            const welcome = messagesContainer.querySelector('.welcome-message');
            if (welcome) welcome.remove();
            
            data.history.forEach(msg => {
                addMessage(msg.role, msg.content, msg.tool_calls);
            });
        }
    } catch (e) {
        console.error('Failed to load history:', e);
    }
}

// Suggestions
document.querySelectorAll('.suggestion').forEach(btn => {
    btn.addEventListener('click', () => {
        messageInput.value = btn.textContent.replace(/^"|"$/g, '');
        messageInput.focus();
    });
});

// === Panels ===
const filesPanel = document.getElementById('files-panel');
const settingsPanel = document.getElementById('settings-panel');

document.getElementById('files-btn').addEventListener('click', () => {
    settingsPanel.classList.remove('active');
    filesPanel.classList.toggle('active');
    if (filesPanel.classList.contains('active')) {
        loadFiles();
    }
});

document.getElementById('settings-btn').addEventListener('click', () => {
    filesPanel.classList.remove('active');
    settingsPanel.classList.toggle('active');
    if (settingsPanel.classList.contains('active') && currentUser) {
        document.getElementById('api-key-display').textContent = currentUser.api_key || 'Not available';
    }
});

document.querySelectorAll('.close-panel').forEach(btn => {
    btn.addEventListener('click', () => {
        filesPanel.classList.remove('active');
        settingsPanel.classList.remove('active');
    });
});

// Copy API key
document.getElementById('copy-key-btn').addEventListener('click', () => {
    const key = document.getElementById('api-key-display').textContent;
    navigator.clipboard.writeText(key);
    document.getElementById('copy-key-btn').textContent = 'Copied!';
    setTimeout(() => {
        document.getElementById('copy-key-btn').textContent = 'Copy';
    }, 2000);
});

// Change Gemini key
document.getElementById('change-key-btn').addEventListener('click', () => {
    settingsPanel.classList.remove('active');
    showScreen('setup');
});

// Clear history
document.getElementById('clear-history-btn').addEventListener('click', async () => {
    if (!confirm('Clear all chat history?')) return;
    
    try {
        await apiRequest('/chat/clear', { method: 'POST' });
        messagesContainer.innerHTML = `
            <div class="welcome-message">
                <div class="logo-icon large">Δ</div>
                <h2>Welcome to DELTA3</h2>
                <p>I can help you write, run, and debug code. Try asking me to:</p>
                <div class="suggestions">
                    <button class="suggestion">"Write a Python script that finds prime numbers"</button>
                    <button class="suggestion">"Create a simple web scraper"</button>
                    <button class="suggestion">"Build a calculator with tests"</button>
                </div>
            </div>
        `;
        
        // Re-attach suggestion handlers
        document.querySelectorAll('.suggestion').forEach(btn => {
            btn.addEventListener('click', () => {
                messageInput.value = btn.textContent.replace(/^"|"$/g, '');
                messageInput.focus();
            });
        });
    } catch (e) {
        alert('Failed to clear history: ' + e.message);
    }
});

// === Files ===
async function loadFiles() {
    const filesList = document.getElementById('files-list');
    
    try {
        const data = await apiRequest('/files/list');
        
        if (!data.files || data.files.length === 0) {
            filesList.innerHTML = '<p class="empty-state">No files yet. Chat with the AI to create some!</p>';
            return;
        }
        
        filesList.innerHTML = data.files.map(file => `
            <div class="file-item" data-path="${file.name}">
                <span class="icon">${file.type === 'directory' ? '📁' : '📄'}</span>
                <span class="name">${file.name}</span>
                ${file.size ? `<span class="size">${formatSize(file.size)}</span>` : ''}
            </div>
        `).join('');
        
        // Add click handlers
        filesList.querySelectorAll('.file-item').forEach(item => {
            item.addEventListener('click', () => {
                const path = item.dataset.path;
                messageInput.value = `Show me the contents of ${path}`;
                messageInput.focus();
                filesPanel.classList.remove('active');
            });
        });
    } catch (e) {
        filesList.innerHTML = `<p class="empty-state">Error loading files: ${e.message}</p>`;
    }
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// === Initialize ===
checkAuth();
