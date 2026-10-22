/**
 * AI Knowledge Hub - 工具函数
 */

// === Toast ===
function showToast(message, type = 'info', duration = 3000) {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success' ? ICONS.check :
                 type === 'error' ? ICONS.alert :
                 type === 'warning' ? ICONS.alert : ICONS.info;

    toast.innerHTML = `${icon}<span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        toast.style.transition = 'all 300ms ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// === HTML Escape ===
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// === Simple Markdown Renderer ===
function renderMarkdown(md) {
    if (!md) return '';

    let html = escapeHtml(md);

    // Code blocks (```)
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (m, lang, code) => {
        return `<pre><code>${code.trim()}</code></pre>`;
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

    // Lists
    html = html.replace(/^[\s]*[-*] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/^[\s]*(\d+)\. (.+)$/gm, '<li>$2</li>');
    html = html.replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, '<ul>$1</ul>');

    // Blockquote
    html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

    // Paragraphs / Line breaks
    html = html.split(/\n\n+/).map(block => {
        if (block.match(/^<(h[1-6]|ul|ol|pre|blockquote|table)/)) return block;
        return `<p>${block.replace(/\n/g, '<br>')}</p>`;
    }).join('\n');

    return html;
}

// === Format Stars ===
function formatStars(n) {
    if (!n) return '0';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return n.toString();
}

// === Format Date ===
function formatDate(d) {
    const date = new Date(d);
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}

// === Debounce ===
function debounce(fn, delay = 300) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// === Copy to Clipboard ===
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('已复制到剪贴板', 'success');
    } catch {
        showToast('复制失败', 'error');
    }
}
