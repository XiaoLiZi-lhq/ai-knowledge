/**
 * AI Knowledge Hub - API 客户端
 * 统一封装所有 API 请求
 */

const API_BASE = '/api/v1';
const API_KEY = localStorage.getItem('akh_api_key') || 'ak-hub-local-2026';

class ApiClient {
    constructor() {
        this.base = API_BASE;
        this.apiKey = API_KEY;
    }

    async request(path, options = {}) {
        const url = `${this.base}${path}`;
        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.apiKey}`,
            ...options.headers,
        };

        try {
            const resp = await fetch(url, { ...options, headers });

            if (resp.status === 401 || resp.status === 403) {
                showToast('API Key 无效或未授权', 'error');
                throw new Error('Unauthorized');
            }

            if (!resp.ok) {
                const error = await resp.json().catch(() => ({ detail: resp.statusText }));
                throw new Error(error.detail || `HTTP ${resp.status}`);
            }

            return await resp.json();
        } catch (err) {
            if (err.message === 'Failed to fetch') {
                showToast('无法连接服务器，请检查服务是否运行', 'error');
            }
            throw err;
        }
    }

    // Health
    async health() {
        return this.request('/health');
    }

    // Chat
    async chat(query, history = null) {
        return this.request('/chat', {
            method: 'POST',
            body: JSON.stringify({ query, history }),
        });
    }

    // Quiz
    async generateQuiz(topic = '', count = 5, type = 'mixed') {
        return this.request('/quiz/generate', {
            method: 'POST',
            body: JSON.stringify({ topic, count, type }),
        });
    }

    async submitQuiz(answers) {
        return this.request('/quiz/submit', {
            method: 'POST',
            body: JSON.stringify({ answers }),
        });
    }

    // Gaps
    async scanGaps(domain = '') {
        return this.request(`/gaps/scan?domain=${encodeURIComponent(domain)}`);
    }

    // Plan
    async generatePlan(goal, durationDays = 14) {
        return this.request('/plan/generate', {
            method: 'POST',
            body: JSON.stringify({ goal, duration_days: durationDays }),
        });
    }

    // GitHub Hot
    async getHotToday() {
        return this.request('/hot/today');
    }

    async collectHot() {
        return this.request('/hot/collect', { method: 'POST' });
    }

    // Notes
    async syncNotes(force = false) {
        return this.request('/notes/sync', {
            method: 'POST',
            body: JSON.stringify({ force }),
        });
    }

    async organizeNote(notePath) {
        return this.request('/notes/organize', {
            method: 'POST',
            body: JSON.stringify({ note_path: notePath }),
        });
    }

    // 桌面投递箱
    async syncInbox(force = false) {
        return this.request('/sync/inbox', {
            method: 'POST',
            body: JSON.stringify({ force }),
        });
    }

    async previewInbox() {
        return this.request('/sync/inbox/preview');
    }

    // WorkBuddy 跨空间同步
    async syncWorkBuddy(force = false) {
        return this.request('/sync/workbuddy', {
            method: 'POST',
            body: JSON.stringify({ force }),
        });
    }

    async previewWorkBuddy() {
        return this.request('/sync/workbuddy/preview');
    }

    // 学习行为统计
    async getLearningStats(days = 30) {
        return this.request(`/learning/stats?days=${days}`);
    }
}

const api = new ApiClient();
