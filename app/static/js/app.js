/**
 * AI Knowledge Hub - 主应用
 */

// === 全局状态 ===
const App = {
    currentPage: 'dashboard',
    chatHistory: [],
    quizData: null,
    quizAnswers: {},
};

// === 导航 ===
function navigate(page) {
    // 更新导航激活状态
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });

    // 切换页面
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === `page-${page}`);
    });

    App.currentPage = page;

    // 更新页面标题
    const titles = {
        dashboard: { title: '仪表盘', subtitle: '系统状态和概览' },
        chat: { title: '知识问答', subtitle: '基于 Obsidian Vault 的 RAG 检索问答' },
        github: { title: 'GitHub 趋势', subtitle: '每日热门项目追踪' },
        quiz: { title: 'AI 出题', subtitle: '基于知识库自动生成测验题' },
        gaps: { title: '知识盲区', subtitle: '扫描知识覆盖度和缺口' },
        plan: { title: '学习计划', subtitle: 'AI 驱动的个性化学习路径' },
        notes: { title: '笔记管理', subtitle: 'Obsidian Vault 同步与整理' },
        learning: { title: '学习中心', subtitle: '投递箱同步与学习行为分析' },
        settings: { title: '设置', subtitle: '系统配置' },
    };

    const t = titles[page] || titles.dashboard;
    document.getElementById('page-title').textContent = t.title;
    document.getElementById('page-subtitle').textContent = t.subtitle;

    // 页面加载回调
    if (page === 'dashboard') loadDashboard();
    if (page === 'github') loadGitHub();
    if (page === 'gaps') loadGaps();
    if (page === 'learning') loadLearning();
}

// === 健康检查 ===
async function checkHealth() {
    const statusEl = document.getElementById('sidebar-status');
    try {
        const h = await api.health();
        App.health = h;

        const dotClass = h.status === 'ok' ? 'online' : 'degraded';
        const statusText = h.status === 'ok' ? '运行正常' : '降级模式';
        statusEl.innerHTML = `<span class="status-dot ${dotClass}"></span><span>${statusText}</span>`;
    } catch {
        statusEl.innerHTML = '<span class="status-dot offline"></span><span>服务离线</span>';
    }
}

// === Dashboard ===
async function loadDashboard() {
    try {
        const h = await api.health();
        App.health = h;

        // 统计数据
        let noteCount = 0;
        let githubCount = 0;
        try {
            noteCount = await getChromaCount('notes');
        } catch {}
        try {
            githubCount = await getChromaCount('github');
        } catch {}

        document.getElementById('stat-model').textContent = h.model || 'qwen3.5:9b';
        document.getElementById('stat-ollama').textContent = h.ollama === 'connected' ? '已连接' : '未连接';
        document.getElementById('stat-chroma').textContent = h.chromadb === 'connected' ? '已连接' : '未连接';
        document.getElementById('stat-notes').textContent = noteCount;
        document.getElementById('stat-github').textContent = githubCount;

        // 状态卡片
        const ollamaEl = document.getElementById('dashboard-ollama');
        if (ollamaEl) {
            ollamaEl.className = `stat-value ${h.ollama === 'connected' ? '' : 'text-danger'}`;
        }
    } catch (err) {
        console.error('Dashboard load error:', err);
    }
}

async function getChromaCount(collection) {
    // 通过 RAG chat 接口间接获取（health 接口不返回计数）
    // 临时方案：显示连接状态即可
    return '-';
}

// === Chat ===
function initChat() {
    const textarea = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');

    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    });

    sendBtn.addEventListener('click', sendChatMessage);

    // 建议词
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            textarea.value = chip.textContent;
            sendChatMessage();
        });
    });
}

async function sendChatMessage() {
    const textarea = document.getElementById('chat-input');
    const query = textarea.value.trim();
    if (!query) return;

    // 清空输入
    textarea.value = '';
    textarea.style.height = 'auto';

    // 隐藏空状态
    const empty = document.getElementById('chat-empty');
    if (empty) empty.style.display = 'none';

    // 渲染用户消息
    appendMessage('user', query);

    // 渲染加载中的助手消息
    const loadingId = appendMessage('assistant', '<div class="loading-dots"><span></span><span></span><span></span></div>');

    try {
        const result = await api.chat(query, App.chatHistory);

        // 记录历史
        App.chatHistory.push(
            { role: 'user', content: query },
            { role: 'assistant', content: result.answer }
        );
        if (App.chatHistory.length > 20) {
            App.chatHistory = App.chatHistory.slice(-20);
        }

        // 更新消息
        updateMessage(loadingId, result.answer, result.sources);
    } catch (err) {
        updateMessage(loadingId, `抱歉，查询失败：${err.message}`);
    }
}

function appendMessage(role, content, sources = []) {
    const container = document.getElementById('chat-messages');
    const id = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 5);

    const avatar = role === 'user' ? '你' : 'AI';
    const avatarIcon = role === 'user' ? '' : ICONS.brain;

    const sourceHtml = sources.length > 0 ? `
        <div class="chat-sources">
            <div style="font-size: 0.75rem; color: var(--color-text-tertiary); margin-bottom: 4px;">参考来源：</div>
            ${sources.map(s => `<span class="source-chip">${ICONS.book}${escapeHtml(s.title)}</span>`).join('')}
        </div>
    ` : '';

    const contentHtml = role === 'assistant'
        ? `<div class="markdown-body">${content.includes('<') ? content : renderMarkdown(content)}</div>${sourceHtml}`
        : content;

    const msg = document.createElement('div');
    msg.className = `chat-message ${role}`;
    msg.id = id;
    msg.innerHTML = `
        <div class="chat-avatar">${role === 'user' ? avatar : avatarIcon}</div>
        <div class="chat-bubble">${contentHtml}</div>
    `;

    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
    return id;
}

function updateMessage(id, content, sources = []) {
    const msg = document.getElementById(id);
    if (!msg) return;

    const bubble = msg.querySelector('.chat-bubble');
    const sourceHtml = sources.length > 0 ? `
        <div class="chat-sources">
            <div style="font-size: 0.75rem; color: var(--color-text-tertiary); margin-bottom: 4px;">参考来源：</div>
            ${sources.map(s => `<span class="source-chip">${ICONS.book}${escapeHtml(s.title)}</span>`).join('')}
        </div>
    ` : '';

    bubble.innerHTML = `<div class="markdown-body">${renderMarkdown(content)}</div>${sourceHtml}`;

    const container = document.getElementById('chat-messages');
    container.scrollTop = container.scrollHeight;
}

// === GitHub ===
async function loadGitHub() {
    const container = document.getElementById('github-grid');
    const loadingEl = document.getElementById('github-loading');

    try {
        const result = await api.getHotToday();

        if (!result.items || result.items.length === 0) {
            container.innerHTML = `
                <div class="empty-state" style="grid-column: 1/-1;">
                    ${ICONS.github}
                    <div class="empty-state-title">暂无今日数据</div>
                    <div class="empty-state-desc">点击下方按钮手动收集今日 GitHub 热点</div>
                    <button class="btn btn-primary" style="margin-top: 16px;" onclick="collectGitHub()">
                        ${ICONS.refresh} 立即收集
                    </button>
                </div>
            `;
            if (loadingEl) loadingEl.style.display = 'none';
            return;
        }

        container.innerHTML = result.items.map(item => {
            const tags = item.tags ? (typeof item.tags === 'string' ? JSON.parse(item.tags) : item.tags) : [];
            return `
                <div class="repo-card">
                    <div class="repo-header">
                        <div>
                            <div class="repo-name">
                                <a href="${item.url}" target="_blank">${escapeHtml(item.repo_name)}</a>
                            </div>
                        </div>
                        <span class="repo-lang">${escapeHtml(item.language || 'Unknown')}</span>
                    </div>
                    <div class="repo-desc">${escapeHtml(item.summary || item.description || '暂无描述')}</div>
                    <div class="repo-meta">
                        <span>${ICONS.star} ${formatStars(item.stars)}</span>
                        <span>${ICONS.link} <a href="${item.url}" target="_blank" style="color:inherit;text-decoration:none;">查看</a></span>
                    </div>
                    ${tags.length > 0 ? `
                        <div class="repo-tags">
                            ${tags.map(t => `<span class="repo-tag">${escapeHtml(t)}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

        if (loadingEl) loadingEl.style.display = 'none';
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state" style="grid-column: 1/-1;">
                ${ICONS.alert}
                <div class="empty-state-title">加载失败</div>
                <div class="empty-state-desc">${escapeHtml(err.message)}</div>
            </div>
        `;
        if (loadingEl) loadingEl.style.display = 'none';
    }
}

async function collectGitHub() {
    showToast('开始后台收集，约 1-3 分钟完成', 'info');
    try {
        await api.collectHot();
        showToast('收集任务已启动', 'success');
        setTimeout(() => loadGitHub(), 30000); // 30秒后刷新
    } catch (err) {
        showToast('收集失败: ' + err.message, 'error');
    }
}

// === Quiz ===
function initQuiz() {
    const generateBtn = document.getElementById('quiz-generate-btn');
    if (generateBtn) {
        generateBtn.addEventListener('click', generateQuiz);
    }
}

async function generateQuiz() {
    const topic = document.getElementById('quiz-topic').value.trim();
    const count = parseInt(document.getElementById('quiz-count').value) || 5;
    const type = document.getElementById('quiz-type').value;

    const container = document.getElementById('quiz-container');
    container.innerHTML = `
        <div class="empty-state">
            <div class="spinner"></div>
            <div class="empty-state-title">AI 正在出题...</div>
            <div class="empty-state-desc">基于知识库内容生成 ${count} 道${type === 'mixed' ? '混合' : type}题</div>
        </div>
    `;

    try {
        const result = await api.generateQuiz(topic, count, type);

        if (result.error) {
            container.innerHTML = `
                <div class="empty-state">
                    ${ICONS.alert}
                    <div class="empty-state-title">生成失败</div>
                    <div class="empty-state-desc">${escapeHtml(result.error)}</div>
                </div>
            `;
            return;
        }

        App.quizData = result;
        App.quizAnswers = {};

        renderQuiz(result);
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state">
                ${ICONS.alert}
                <div class="empty-state-title">出题失败</div>
                <div class="empty-state-desc">${escapeHtml(err.message)}</div>
            </div>
        `;
    }
}

function renderQuiz(data) {
    const container = document.getElementById('quiz-container');
    const questions = data.questions || [];

    if (questions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                ${ICONS.alert}
                <div class="empty-state-title">没有生成题目</div>
            </div>
        `;
        return;
    }

    let html = '';

    questions.forEach((q, qi) => {
        const isChoice = q.type === 'choice';
        const options = q.options || [];

        html += `
            <div class="quiz-card" data-qi="${qi}">
                <div class="quiz-question">
                    <div class="quiz-question-text">
                        ${qi + 1}. [${q.type === 'choice' ? '选择题' : q.type === 'code' ? '代码题' : '简答题'}]
                        ${escapeHtml(q.question)}
                    </div>
                    ${isChoice ? `
                        <div class="quiz-options">
                            ${options.map((opt, oi) => {
                                const letter = String.fromCharCode(65 + oi);
                                return `
                                    <div class="quiz-option" data-qi="${qi}" data-oi="${oi}" onclick="selectAnswer(${qi}, '${letter}')">
                                        <div class="quiz-option-letter">${letter}</div>
                                        <div class="quiz-option-text">${escapeHtml(opt)}</div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    ` : `
                        <textarea class="input" id="quiz-answer-${qi}" rows="3" placeholder="请输入你的答案..."></textarea>
                    `}
                </div>
            </div>
        `;
    });

    html += `
        <div style="text-align: center; padding: 20px;">
            <button class="btn btn-primary btn-lg" onclick="submitQuiz()">
                ${ICONS.check} 提交答案
            </button>
        </div>
    `;

    container.innerHTML = html;
}

function selectAnswer(qi, letter) {
    App.quizAnswers[qi] = letter;

    // 更新 UI
    document.querySelectorAll(`.quiz-option[data-qi="${qi}"]`).forEach(opt => {
        const oi = parseInt(opt.dataset.oi);
        const optLetter = String.fromCharCode(65 + oi);
        opt.classList.toggle('selected', optLetter === letter);
    });
}

async function submitQuiz() {
    const questions = App.quizData?.questions || [];
    if (!questions.length) return;

    const answers = [];
    questions.forEach((q, qi) => {
        if (q.type === 'choice') {
            answers.push({
                question: q.question,
                user_answer: App.quizAnswers[qi] || '',
                correct_answer: q.answer || '',
            });
        } else {
            const textArea = document.getElementById(`quiz-answer-${qi}`);
            answers.push({
                question: q.question,
                user_answer: textArea ? textArea.value.trim() : '',
                correct_answer: q.answer || '',
            });
        }
    });

    try {
        const result = await api.submitQuiz(answers);

        // 显示结果
        questions.forEach((q, qi) => {
            if (q.type === 'choice') {
                const correctLetter = q.answer;
                document.querySelectorAll(`.quiz-option[data-qi="${qi}"]`).forEach(opt => {
                    const oi = parseInt(opt.dataset.oi);
                    const optLetter = String.fromCharCode(65 + oi);
                    opt.classList.remove('selected');

                    if (optLetter === correctLetter) {
                        opt.classList.add('correct');
                    } else if (optLetter === App.quizAnswers[qi]) {
                        opt.classList.add('wrong');
                    }
                });
            }
        });

        showToast(`得分: ${result.score}分 (${result.correct}/${result.total})`, result.score >= 60 ? 'success' : 'warning', 5000);

        // 在顶部显示成绩
        const container = document.getElementById('quiz-container');
        const scoreCard = document.createElement('div');
        scoreCard.className = 'card';
        scoreCard.style.marginBottom = '16px';
        scoreCard.innerHTML = `
            <div class="card-body" style="text-align: center;">
                <div style="font-size: 2.5rem; font-weight: 800; color: ${result.score >= 80 ? 'var(--color-success)' : result.score >= 60 ? 'var(--color-info)' : 'var(--color-danger)'};">${result.score}</div>
                <div style="color: var(--color-text-tertiary); font-size: 0.875rem;">${result.correct} / ${result.total} 正确</div>
            </div>
        `;
        container.insertBefore(scoreCard, container.firstChild);

    } catch (err) {
        showToast('提交失败: ' + err.message, 'error');
    }
}

// === Gaps ===
async function loadGaps() {
    const container = document.getElementById('gaps-container');

    container.innerHTML = `
        <div class="empty-state">
            <div class="spinner"></div>
            <div class="empty-state-title">正在扫描知识盲区...</div>
        </div>
    `;

    try {
        const result = await api.scanGaps();
        renderGaps(result);
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state">
                ${ICONS.alert}
                <div class="empty-state-title">扫描失败</div>
                <div class="empty-state-desc">${escapeHtml(err.message)}</div>
            </div>
        `;
    }
}

function renderGaps(data) {
    const container = document.getElementById('gaps-container');
    const details = data.details || [];

    if (details.length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state-title">无数据</div></div>`;
        return;
    }

    let html = '';

    // 概要
    if (data.total_gaps > 0) {
        html += `
            <div class="card" style="margin-bottom: 20px; border-left: 4px solid var(--color-warning);">
                <div class="card-body" style="display: flex; align-items: center; gap: 12px;">
                    ${ICONS.sparkles}
                    <div>
                        <div style="font-weight: 600; font-size: 0.875rem;">发现 ${data.total_gaps} 个知识盲区</div>
                        <div style="font-size: 0.8125rem; color: var(--color-text-tertiary);">建议优先补充覆盖度较低的知识点</div>
                    </div>
                </div>
            </div>
        `;
    }

    details.forEach(d => {
        const coverage = d.coverage_percent;
        const statusClass = coverage >= 70 ? 'excellent' : coverage >= 50 ? 'good' : 'weak';
        const progressClass = coverage >= 70 ? 'high' : coverage >= 40 ? 'mid' : 'low';

        html += `
            <div class="gap-domain">
                <div class="gap-domain-header">
                    <div class="gap-domain-name">${escapeHtml(d.domain)}</div>
                    <span class="gap-status-badge ${statusClass}">${escapeHtml(d.status)} ${coverage}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill ${progressClass}" style="width: ${coverage}%;"></div>
                </div>
                ${d.gaps && d.gaps.length > 0 ? `
                    <div style="font-size: 0.75rem; color: var(--color-text-tertiary); margin-bottom: 8px;">缺失知识点：</div>
                    <div class="gap-topics">
                        ${d.gaps.map(g => `<span class="gap-topic missing">${escapeHtml(g.topic)}</span>`).join('')}
                    </div>
                ` : `
                    <div style="font-size: 0.75rem; color: var(--color-success);">覆盖良好，无明显盲区</div>
                `}
            </div>
        `;
    });

    container.innerHTML = html;
}

// === Plan ===
function initPlan() {
    const generateBtn = document.getElementById('plan-generate-btn');
    if (generateBtn) {
        generateBtn.addEventListener('click', generatePlan);
    }
}

async function generatePlan() {
    const goal = document.getElementById('plan-goal').value.trim();
    const days = parseInt(document.getElementById('plan-days').value) || 14;

    if (!goal) {
        showToast('请输入学习目标', 'warning');
        return;
    }

    const container = document.getElementById('plan-container');
    container.innerHTML = `
        <div class="empty-state">
            <div class="spinner"></div>
            <div class="empty-state-title">AI 正在生成学习计划...</div>
            <div class="empty-state-desc">基于知识盲区分析为 "${escapeHtml(goal)}" 定制 ${days} 天计划</div>
        </div>
    `;

    try {
        const result = await api.generatePlan(goal, days);

        if (result.error) {
            container.innerHTML = `
                <div class="empty-state">
                    ${ICONS.alert}
                    <div class="empty-state-title">生成失败</div>
                    <div class="empty-state-desc">${escapeHtml(result.error)}</div>
                </div>
            `;
            return;
        }

        renderPlan(result);
        showToast('学习计划已生成并写入 Vault', 'success');
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state">
                ${ICONS.alert}
                <div class="empty-state-title">生成失败</div>
                <div class="empty-state-desc">${escapeHtml(err.message)}</div>
            </div>
        `;
    }
}

function renderPlan(data) {
    const container = document.getElementById('plan-container');
    const weeks = data.weeks || [];

    if (weeks.length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state-title">计划内容为空</div></div>`;
        return;
    }

    let html = `
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-body">
                <h3 style="margin-bottom: 8px;">${escapeHtml(data.title || '学习计划')}</h3>
                <div style="color: var(--color-text-secondary); font-size: 0.875rem;">
                    <strong>目标：</strong>${escapeHtml(data.goal || '')}<br>
                    <strong>周期：</strong>${escapeHtml(data.start_date || '')} ~ ${escapeHtml(data.end_date || '')}
                </div>
            </div>
        </div>
    `;

    weeks.forEach(week => {
        html += `
            <div class="plan-week">
                <div class="plan-week-header">
                    <div class="plan-week-num">${week.week || ''}</div>
                    <div>
                        <div class="plan-week-theme">${escapeHtml(week.theme || '')}</div>
                    </div>
                </div>
                <div class="card">
                    <div class="card-body">
                        ${week.days ? week.days.map(day => `
                            <div class="plan-day">
                                <div class="plan-day-date">${escapeHtml(day.date || '')}</div>
                                <div class="plan-day-task">
                                    ${escapeHtml(day.task || '')}
                                    ${day.estimated_hours ? `<span style="color: var(--color-text-tertiary); font-size: 0.75rem;"> (${day.estimated_hours}h)</span>` : ''}
                                    ${day.resources && day.resources.length > 0 ? `<br><span style="color: var(--color-primary); font-size: 0.75rem;">${day.resources.map(r => escapeHtml(r)).join(' | ')}</span>` : ''}
                                </div>
                            </div>
                        `).join('') : ''}
                        ${week.checkpoint ? `
                            <div style="margin-top: 12px; padding: 12px; background: var(--color-primary-lightest); border-radius: 8px; font-size: 0.8125rem;">
                                <strong>周末检验：</strong>${escapeHtml(week.checkpoint)}
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// === Notes ===
function initNotes() {
    document.getElementById('sync-btn')?.addEventListener('click', syncNotes);
    document.getElementById('organize-btn')?.addEventListener('click', organizeNote);
}

async function syncNotes() {
    const btn = document.getElementById('sync-btn');
    const force = document.getElementById('sync-force')?.checked || false;

    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> 同步中...';

    try {
        const result = await api.syncNotes(force);
        showToast(`同步完成：${result.synced_chunks} 个文档块`, 'success');
        document.getElementById('sync-result').innerHTML = `
            <div class="card" style="margin-top: 16px;">
                <div class="card-body" style="display: flex; align-items: center; gap: 12px;">
                    ${ICONS.check}
                    <div>
                        <div style="font-weight: 600;">同步成功</div>
                        <div style="color: var(--color-text-tertiary); font-size: 0.8125rem;">
                            已索引 ${result.synced_chunks} 个文档块到向量数据库
                        </div>
                    </div>
                </div>
            </div>
        `;
    } catch (err) {
        showToast('同步失败: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = ICONS.refresh + ' 同步 Vault';
    }
}

async function organizeNote() {
    const path = document.getElementById('organize-path').value.trim();
    if (!path) {
        showToast('请输入笔记路径', 'warning');
        return;
    }

    const btn = document.getElementById('organize-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> 整理中...';

    try {
        const result = await api.organizeNote(path);
        showToast('笔记整理完成', 'success');
        document.getElementById('organize-result').innerHTML = `
            <div class="card" style="margin-top: 16px;">
                <div class="card-body">
                    <div style="font-weight: 600; margin-bottom: 8px;">整理结果</div>
                    <div class="markdown-body">${renderMarkdown(JSON.stringify(result, null, 2))}</div>
                </div>
            </div>
        `;
    } catch (err) {
        showToast('整理失败: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = ICONS.sparkles + ' AI 整理';
    }
}

// === 学习中心 ===
async function loadLearning() {
    try {
        const stats = await api.getLearningStats(30);
        renderLearningStats(stats);
    } catch {
        // 统计加载失败不阻塞页面
    }
}

function renderLearningStats(stats) {
    document.getElementById('learn-total-notes').textContent = stats.total_notes || 0;
    document.getElementById('learn-streak').textContent = stats.streak || 0;
    document.getElementById('learn-total-tags').textContent = stats.total_tags || 0;
    document.getElementById('learn-total-sources').textContent = stats.total_sources || 0;

    // 学习行为图表
    const chartsEl = document.getElementById('learning-charts');
    if (!stats.total_notes || stats.total_notes === 0) {
        chartsEl.innerHTML = '<p style="color: var(--color-text-secondary); font-size: 0.875rem;">暂无学习数据，导入笔记后将自动生成统计。</p>';
    } else {
        chartsEl.innerHTML = renderTagChart(stats.tag_distribution || []) + renderSourceChart(stats.source_distribution || []) + renderDailyChart(stats.daily_counts || []);
    }

    // 最近笔记
    const latestEl = document.getElementById('latest-notes');
    if (!stats.latest_notes || stats.latest_notes.length === 0) {
        latestEl.innerHTML = '<p style="color: var(--color-text-secondary); font-size: 0.875rem;">暂无笔记</p>';
    } else {
        latestEl.innerHTML = stats.latest_notes.map(n => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--color-border);">
                <div>
                    <div style="font-weight: 500;">${escapeHtml(n.title)}</div>
                    <div style="font-size: 0.8125rem; color: var(--color-text-tertiary);">来源: ${escapeHtml(n.source)}</div>
                </div>
                <div style="font-size: 0.8125rem; color: var(--color-text-tertiary);">${n.learn_date}</div>
            </div>
        `).join('');
    }
}

function renderTagChart(tags) {
    if (!tags.length) return '';
    const max = tags[0].count;
    const colors = ['var(--color-primary)', 'var(--color-success)', 'var(--color-warning)', 'var(--color-info)', 'var(--color-secondary)'];
    const bars = tags.slice(0, 10).map((t, i) => {
        const pct = Math.max(8, (t.count / max) * 100);
        return `
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                <span style="width: 120px; font-size: 0.8125rem; color: var(--color-text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(t.tag)}</span>
                <div style="flex: 1; background: var(--color-bg-secondary); border-radius: 4px; height: 22px; overflow: hidden;">
                    <div style="width: ${pct}%; height: 100%; background: ${colors[i % colors.length]}; border-radius: 4px; display: flex; align-items: center; padding-left: 8px; color: white; font-size: 0.75rem; font-weight: 600;">${t.count}</div>
                </div>
            </div>
        `;
    }).join('');
    return `
        <div style="margin-bottom: 20px;">
            <div style="font-weight: 600; margin-bottom: 12px;">主题分布</div>
            ${bars}
        </div>
    `;
}

function renderSourceChart(sources) {
    if (!sources.length) return '';
    const max = sources[0].count;
    const bars = sources.map((s, i) => {
        const pct = Math.max(8, (s.count / max) * 100);
        return `
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                <span style="width: 120px; font-size: 0.8125rem; color: var(--color-text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(s.source)}</span>
                <div style="flex: 1; background: var(--color-bg-secondary); border-radius: 4px; height: 22px; overflow: hidden;">
                    <div style="width: ${pct}%; height: 100%; background: var(--color-info); border-radius: 4px; display: flex; align-items: center; padding-left: 8px; color: white; font-size: 0.75rem; font-weight: 600;">${s.count}</div>
                </div>
            </div>
        `;
    }).join('');
    return `
        <div style="margin-bottom: 20px;">
            <div style="font-weight: 600; margin-bottom: 12px;">来源分布</div>
            ${bars}
        </div>
    `;
}

function renderDailyChart(daily) {
    if (!daily.length) return '';
    const max = Math.max(...daily.map(d => d.count));
    const bars = daily.map(d => {
        const pct = Math.max(4, (d.count / max) * 100);
        return `
            <div style="display: inline-flex; flex-direction: column; align-items: center; gap: 4px; margin-right: 4px; vertical-align: bottom;">
                <span style="font-size: 0.6875rem; color: var(--color-text-tertiary);">${d.count}</span>
                <div style="width: 16px; background: var(--color-primary); border-radius: 2px; height: ${Math.max(4, pct * 0.6)}px;"></div>
                <span style="font-size: 0.625rem; color: var(--color-text-tertiary);">${d.date.slice(5)}</span>
            </div>
        `;
    }).join('');
    return `
        <div>
            <div style="font-weight: 600; margin-bottom: 12px;">每日学习量趋势</div>
            <div style="display: flex; align-items: flex-end; gap: 2px; overflow-x: auto; padding-bottom: 8px;">
                ${bars}
            </div>
        </div>
    `;
}

async function previewInbox() {
    const el = document.getElementById('inbox-content');
    el.innerHTML = '<div class="spinner"></div><span style="margin-left: 8px; color: var(--color-text-secondary);">扫描中...</span>';
    try {
        const result = await api.previewInbox();
        if (result.total_files === 0) {
            el.innerHTML = '<p style="color: var(--color-text-secondary); font-size: 0.875rem;">投递箱为空（~/Desktop/LearningInbox/）</p><p style="color: var(--color-text-tertiary); font-size: 0.8125rem; margin-top: 8px;">把 .md 笔记文件放到投递箱目录即可。</p>';
            return;
        }
        const fileRows = result.files.map(f => `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--color-border);">
                <div style="flex: 1; min-width: 0;">
                    <div style="font-weight: 500; font-size: 0.875rem;">${escapeHtml(f.title)}</div>
                    <div style="font-size: 0.75rem; color: var(--color-text-tertiary);">${escapeHtml(f.file_name)} | ${escapeHtml(f.source)} | ${(f.size / 1024).toFixed(1)}KB</div>
                </div>
                <span class="badge ${f.already_synced ? 'badge-secondary' : 'badge-primary'}">${f.already_synced ? '已导入' : '待导入'}</span>
            </div>
        `).join('');
        el.innerHTML = `
            <div style="margin-bottom: 12px; font-size: 0.875rem; color: var(--color-text-secondary);">
                共 ${result.total_files} 个文件 | 待导入 ${result.pending} | 已导入 ${result.already_synced}
            </div>
            ${fileRows}
        `;
    } catch (err) {
        el.innerHTML = '<p style="color: var(--color-danger); font-size: 0.875rem;">加载失败: ' + escapeHtml(err.message) + '</p>';
    }
}

async function syncInbox() {
    const btn = document.getElementById('btn-sync-inbox');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> 导入中...';
    try {
        const result = await api.syncInbox(false);
        showToast(`导入完成: ${result.imported} 篇, 跳过 ${result.skipped} 篇`, 'success');
        document.getElementById('inbox-content').innerHTML = `
            <div style="display: flex; gap: 20px; margin-bottom: 16px;">
                <div><span style="font-size: 1.5rem; font-weight: 700; color: var(--color-success);">${result.imported}</span> <span style="font-size: 0.8125rem; color: var(--color-text-tertiary);">已导入</span></div>
                <div><span style="font-size: 1.5rem; font-weight: 700; color: var(--color-text-tertiary);">${result.skipped}</span> <span style="font-size: 0.8125rem; color: var(--color-text-tertiary);">已跳过</span></div>
                <div><span style="font-size: 1.5rem; font-weight: 700; color: var(--color-text-tertiary);">${result.errors}</span> <span style="font-size: 0.8125rem; color: var(--color-text-tertiary);">错误</span></div>
            </div>
            ${(result.details || []).filter(d => d.status === 'imported').map(d => `
                <div style="padding: 6px 0; font-size: 0.8125rem; border-bottom: 1px solid var(--color-border);">
                    <strong>${escapeHtml(d.title)}</strong>
                    <span style="color: var(--color-text-tertiary);"> - ${escapeHtml(d.source)} [${(d.tags || []).join(', ')}]</span>
                </div>
            `).join('')}
        `;
        loadLearning();
    } catch (err) {
        showToast('导入失败: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> 扫描导入';
    }
}

async function previewWorkBuddy() {
    const el = document.getElementById('workbuddy-content');
    el.innerHTML = '<div class="spinner"></div><span style="margin-left: 8px; color: var(--color-text-secondary);">扫描所有空间...</span>';
    try {
        const result = await api.previewWorkBuddy();
        if (result.total_files === 0) {
            el.innerHTML = '<p style="color: var(--color-text-secondary); font-size: 0.875rem;">未发现 WorkBuddy 空间记忆文件</p>';
            return;
        }
        el.innerHTML = `
            <div style="margin-bottom: 12px; font-size: 0.875rem; color: var(--color-text-secondary);">
                ${result.workspaces.length} 个空间 | ${result.total_files} 个文件 | 待同步 ${result.pending}
            </div>
            <div style="font-size: 0.8125rem; color: var(--color-text-tertiary);">${result.workspaces.join(', ')}</div>
        `;
    } catch (err) {
        el.innerHTML = '<p style="color: var(--color-danger); font-size: 0.875rem;">加载失败: ' + escapeHtml(err.message) + '</p>';
    }
}

async function syncWorkBuddy() {
    const btn = document.getElementById('btn-sync-workbuddy');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> 同步中...';
    try {
        const result = await api.syncWorkBuddy(false);
        showToast(`WorkBuddy 同步完成: 导入 ${result.imported}, 跳过 ${result.skipped}`, 'success');
        document.getElementById('workbuddy-content').innerHTML = `
            <div style="display: flex; gap: 20px; margin-bottom: 12px;">
                <div><span style="font-size: 1.5rem; font-weight: 700; color: var(--color-success);">${result.imported}</span> <span style="font-size: 0.8125rem;">导入</span></div>
                <div><span style="font-size: 1.5rem; font-weight: 700; color: var(--color-text-tertiary);">${result.skipped}</span> <span style="font-size: 0.8125rem;">跳过</span></div>
                <div><span style="font-size: 1.5rem; font-weight: 700; color: var(--color-text-tertiary);">${result.errors}</span> <span style="font-size: 0.8125rem;">错误</span></div>
            </div>
            <div style="font-size: 0.75rem; color: var(--color-text-tertiary);">用时 ${result.duration_seconds}s</div>
        `;
    } catch (err) {
        showToast('同步失败: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> 全量同步';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

// === 初始化 ===
document.addEventListener('DOMContentLoaded', () => {
    // 导航绑定
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navigate(item.dataset.page);
        });
    });

    // 健康检查
    checkHealth();
    setInterval(checkHealth, 30000); // 每30秒检查一次

    // 初始化各页面
    initChat();
    initQuiz();
    initPlan();
    initNotes();

    // 加载仪表盘
    loadDashboard();
});
