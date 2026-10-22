# AI Knowledge Hub - 项目分析报告

> 审查日期：2026-08-10
> 审查范围：全部后端代码 + 前端代码 + 配置 + 测试 + 脚本

---

## 一、项目总览

| 维度 | 现状 |
|------|------|
| 技术栈 | FastAPI + ChromaDB + Ollama + DeepSeek + SQLite |
| 代码量 | 后端 ~1200 行 Python / 前端 ~1500 行 HTML+CSS+JS |
| 测试覆盖 | 17 个测试，覆盖配置/分块/路由/微信/出题等 |
| 功能完成度 | 核心功能可运行，部分功能缺少实际数据验证 |

**总体评价**：项目架构清晰，分层合理，三级嵌入降级策略是亮点。以下按严重程度分级列出改进建议。

---

## 二、P0 - 安全问题（必须修复）

### 2.1 CORS 完全开放

**文件**：`app/main.py` 第 122-128 行

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # 任意来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**风险**：`allow_origins=["*"]` + `allow_credentials=True` 是危险组合。虽然 FastAPI 在这个组合下会忽略 credentials，但仍然意味着任何网站都能调用你的 API。

**建议**：
```python
allow_origins=[
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # Obsidian 插件来源
    "app://obsidian.md",
]
```

### 2.2 API Key 硬编码到前端

**文件**：`app/static/js/api.js` 第 7 行

```javascript
const API_KEY = localStorage.getItem('akh_api_key') || 'ak-hub-local-2026';
```

**风险**：API Key 写死在前端 JS 中，任何人查看源码即可获取。虽然只是本地服务，但如果部署到公网则等于无认证。

**建议**：
- 本地单用户场景：前端不发送 API Key，后端对同源请求（localhost）免认证
- 公网部署场景：加 Session/JWT 认证，API Key 只在后端使用

### 2.3 DeepSeek API Key 已泄露

**风险**：API Key 在对话中明文出现过，应视为已泄露。

**建议**：去 DeepSeek 平台重新生成，旧 Key 立即作废。

---

## 三、P1 - 功能缺陷（应该修复）

### 3.1 飞书通知无法工作

**文件**：`app/integrations/feishu_notifier.py` 第 13-14 行

```python
def __init__(self, webhook_url: str = ""):
    self.webhook_url = webhook_url or ""  # 从配置加载 ← 实际没加载
```

**问题**：`webhook_url` 永远是空字符串，`.env` 中也没有飞书 webhook 配置项。`send_text` 和 `send_card` 都会直接返回 `False`。

**建议**：
```python
# .env 新增
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# config.py 新增
FEISHU_WEBHOOK_URL: str = os.getenv("FEISHU_WEBHOOK_URL", "")

# feishu_notifier.py
feishu_notifier = FeishuNotifier(webhook_url=settings.FEISHU_WEBHOOK_URL)
```

### 3.2 RAG 同步存在重复索引问题

**文件**：`app/core/rag.py` 第 78-107 行

**问题**：`index_vault` 用 `ids = [f"{md_file.stem}_{i}" for i in range(len(docs))]` 生成 ID。如果两个不同路径的文件同名（如 `01-Notes/README.md` 和 `02-Resources/README.md`），它们的 chunk 会互相覆盖。

**建议**：用文件路径的哈希作为 ID 前缀：
```python
import hashlib
path_hash = hashlib.md5(file_key.encode()).hexdigest()[:8]
ids = [f"{path_hash}_{i}" for i in range(len(docs))]
```

### 3.3 RAG 检索的 BM25 实现过于简化

**文件**：`app/core/rag.py` 第 147-154 行

```python
def _bm25_score(self, query: str, document: str) -> float:
    query_terms = set(query.lower().split())  # 空格分词，对中文无效
    ...
```

**问题**：`split()` 按空格切分，中文查询几乎不会产生有效的 term 匹配。BM25 重排对中文基本是摆设。

**建议**：用 jieba 分词（项目已有依赖）：
```python
import jieba
query_terms = set(jieba.cut_for_search(query.lower()))
doc_terms = list(jieba.cut_for_search(document.lower()))
```

### 3.4 缺少流式聊天 API 端点

**问题**：`app/core/rag.py` 已实现了 `answer_stream` 生成器方法，但 `routes.py` 没有暴露流式接口。前端每次问答都要等待完整响应，用户体验差（尤其本地 9B 模型响应慢）。

**建议**：新增 SSE 流式端点：
```python
from fastapi.responses import StreamingResponse

@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, auth: bool = Depends(verify_api_key)):
    def generate():
        for token in rag.answer_stream(req.query, req.history):
            yield f"data: {json.dumps({'token': token})}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 3.5 GitHub 热点收集的 CSS 选择器可能失效

**文件**：`app/services/github_collector.py` 第 68 行

```python
items = soup.select("article.Box-row")
```

**问题**：GitHub 页面结构变更频繁，硬编码 CSS 选择器非常脆弱。

**建议**：
1. 改用 GitHub REST API `/search/repositories?sort=stars&order=desc`（更稳定）
2. 或用第三方 API 如 `https://api.gitterapp.com/repositories`
3. 添加选择器失效的异常处理和降级逻辑

### 3.6 知识盲区扫描覆盖度评估过于粗糙

**文件**：`app/services/ai_tutor.py` 第 257-271 行

**问题**：覆盖度评估仅基于标签和标题的字符串包含匹配。如果笔记内容详细覆盖了某个知识点但标题中没有关键词，会被误判为盲区。

**建议**：增加 ChromaDB 向量检索覆盖率——用知识点作为 query 检索，如果检索距离 < 阈值则认为有覆盖。

---

## 四、P2 - 代码质量改进

### 4.1 前端缺少错误边界和加载状态

**文件**：`app/static/js/app.js`

**问题**：
- `loadGitHub()` 失败后没有重试按钮
- 长时间 LLM 调用（出题、计划生成）没有超时处理
- 没有全局的请求错误拦截

### 4.2 配置缺少验证

**文件**：`app/config.py`

**问题**：启动时不验证关键路径是否存在（如 Vault 路径、ChromaDB 路径），用户可能到运行时才发现问题。

**建议**：加启动校验：
```python
def validate(self):
    issues = []
    if not self.vault_path_obj.exists():
        issues.append(f"Vault 路径不存在: {self.vault_path_obj}")
    if not self.DEEPSEEK_API_KEY and not self.check_ollama():
        issues.append("Ollama 和 DeepSeek 均不可用")
    return issues
```

### 4.3 LLM JSON 解析重复代码

**文件**：`ai_tutor.py` 中 `QuizGenerator.generate` 和 `PlanGenerator.generate` 各自有一份几乎相同的 JSON 清理 + `fix_newlines_in_strings` 函数。

**建议**：提取到 `app/core/utils.py` 作为公共函数：
```python
def parse_llm_json(raw: str) -> dict:
    """清理 LLM 输出并解析 JSON"""
    ...
```

### 4.4 全局单例的初始化顺序依赖

**问题**：`rag.py` 在模块级别创建 `rag = RAGPipeline()`，但 ChromaDB 客户端是懒加载的。如果 ChromaDB 目录不存在，首次访问才会报错。多个模块相互 import 这些单例（`rag` → `llm_service` → `settings`），依赖链较长。

---

## 五、P3 - 功能增强建议

### 5.1 推荐新增

| 功能 | 价值 | 复杂度 |
|------|------|--------|
| **流式聊天** | 本地模型响应慢，流式输出大幅改善体验 | 低（后端已实现） |
| **聊天历史持久化** | 当前刷新即丢失，用 SQLite 存对话记录 | 中 |
| **个人 GitHub 项目展示** | 你之前提到的需求 | 低 |
| **笔记全文搜索** | 当前只能 RAG 语义搜索，加一个精确全文搜索 | 中 |
| **知识图谱可视化** | 笔记间的双链关系可视化 | 高 |
| **导入文档向量化** | 支持 PDF/Word 导入，不只是 Markdown | 中 |
| **多 Vault 支持** | 切换不同知识库 | 低 |

### 5.2 前端增强

| 改进 | 说明 |
|------|------|
| 暗色主题切换 | CSS 变量已就绪，只需加 toggle |
| 移动端适配优化 | 当前侧边栏在手机上隐藏，需要汉堡菜单 |
| PWA 支持 | 离线可用、可安装到桌面 |
| 快捷键支持 | Cmd+K 打开搜索，Cmd+Enter 发送消息 |

### 5.3 运维增强

| 改进 | 说明 |
|------|------|
| **Docker 化** | Dockerfile + docker-compose，一键部署 |
| **健康检查 API 增强** | 返回向量数量、笔记数量等统计 |
| **日志系统** | 用 loguru 替代 print，可配置日志级别 |
| **Ollama 模型管理** | API 接口拉取/切换模型 |

---

## 六、测试改进

### 当前覆盖
- 配置加载 ✅
- 文档分块 ✅
- BM25 计算 ✅
- 微信路由 ✅
- 出题评分 ✅
- API 路由（health/chat unauthorized）✅

### 缺失覆盖（建议补充）
- [ ] RAG 完整问答流程（mock LLM）
- [ ] 嵌入向量生成 + ChromaDB 读写
- [ ] GitHub Collector（mock HTTP）
- [ ] 学习计划生成 + Markdown 写入
- [ ] 笔记整理 + auto_tag
- [ ] 前端 API 客户端（mock fetch）

---

## 七、优先级排序（建议执行顺序）

| 优先级 | 任务 | 预估工作量 |
|--------|------|-----------|
| P0 | 重新生成 DeepSeek API Key | 5 分钟 |
| P0 | 收紧 CORS 策略 | 10 分钟 |
| P1 | 修复飞书 webhook 配置 | 15 分钟 |
| P1 | 修复 ChromaDB ID 冲突 | 10 分钟 |
| P1 | BM25 改用 jieba 分词 | 15 分钟 |
| P1 | 新增流式聊天 API + 前端对接 | 1 小时 |
| P1 | GitHub 抓取改用 API 或加降级 | 30 分钟 |
| P2 | 提取 JSON 解析公共函数 | 20 分钟 |
| P2 | 启动时配置校验 | 20 分钟 |
| P2 | 前端暗色主题 | 30 分钟 |
| P3 | Docker 化 | 1 小时 |
| P3 | 聊天历史持久化 | 2 小时 |
