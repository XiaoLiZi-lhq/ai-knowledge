# AI Knowledge Hub - 部署指南

## 环境要求

- macOS（Apple Silicon 推荐，16GB+ 内存）
- Python 3.11+
- Ollama（已安装）
- Obsidian（已安装）
- Git

## 一、首次部署

### 1. 克隆项目并初始化 Git

```bash
# 克隆你的 GitHub 私有仓库
git clone git@github.com:<你的用户名>/ai-knowledge-hub.git
cd ai-knowledge-hub

# 如果是从零开始，先在 GitHub 创建私有仓库，然后：
git remote add origin git@github.com:<你的用户名>/ai-knowledge-hub.git
```

### 2. Python 环境

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写：
- `API_KEY`：自定义一个本地 API 密钥
- `DEEPSEEK_API_KEY`：从 https://platform.deepseek.com 获取
- `VAULT_PATH`：Obsidian Vault 路径
- `WECHAT_WHITE_LIST`：你的微信 wxid

### 4. 确保 Ollama 运行

```bash
# 启动 Ollama（关键：设置 CORS 允许跨域）
OLLAMA_ORIGINS="*" ollama serve

# 另一个终端拉取模型（如果还没有）
ollama pull qwen3.5:9b
ollama pull nomic-embed-text
```

### 5. 初始化 Obsidian Vault

```bash
python scripts/init_vault.py --path ~/Documents/MyVault
```

然后用 Obsidian 打开 `~/Documents/MyVault`。

### 6. 配置 Obsidian 插件

在 Obsidian 中安装以下插件：

| 插件 | 配置 |
|------|------|
| **Templater** | 模板文件夹指向 `03-Templates` |
| **Dataview** | 启用 JavaScript 查询 |
| **Obsidian Git** | 自动提交间隔 10 分钟，自动推送 |
| **Smart Connections** | 嵌入模型选 Ollama nomic-embed-text |

Obsidian Git 插件配置：
1. 设置 Vault 的 Git 远程仓库（另一个私有仓库）
2. 提交间隔：10 分钟
3. 自动推送：开启
4. 启动时拉取：开启

### 7. 首次提交代码到 GitHub

```bash
./scripts/git-commit.sh "feat: 初始项目结构搭建完成"
```

### 8. 启动服务

```bash
python -m app.main
```

访问 http://localhost:8000/docs 查看 API 文档。

---

## 二、日常使用

### 提交代码（每次改动后）

```bash
# 带说明的提交（推荐）
./scripts/git-commit.sh "feat: 新增盲区扫描优化逻辑"

# 自动备份提交
./scripts/git-commit.sh
```

脚本会自动：
1. 检查变更文件
2. 附带时间戳和提交说明
3. commit + push 到 GitHub

### GitHub Actions 自动备份

项目配置了 GitHub Actions（`.github/workflows/auto-backup.yml`）：
- 每天北京时间 23:00 自动检查并提交未保存的变更
- 作为最后一道防线，防止遗漏

### 微信接入（Mac 环境）

Mac 无法直接使用 wcferry，推荐方案：

**方案 A：企业微信 Webhook（最稳定）**
1. 注册企业微信，创建自建应用
2. 配置回调 URL 指向你的 FastAPI 服务
3. 在 `.env` 中配置企业微信凭证

**方案 B：微信测试号**
1. 申请微信公众平台接口测试号
2. 配置消息推送 URL
3. 用测试号在微信中与助手对话

**方案 C：iOS 快捷指令**
1. 创建 iOS Shortcut，发 HTTP 请求到 FastAPI
2. 添加到主屏幕，快速提问

---

## 三、定时任务

服务启动后自动运行以下定时任务：

| 任务 | 时间 | 说明 |
|------|------|------|
| GitHub 热点收集 | 每日 08:00 | 抓取 Trending，AI 摘要，写入 Vault |
| Vault 向量化同步 | 每日 02:00 | 扫描 Vault，增量更新向量库 |

---

## 四、故障排查

### Ollama 连接失败
```bash
# 检查 Ollama 是否运行
curl http://localhost:11434/api/tags

# 确保 CORS 设置
OLLAMA_ORIGINS="*" ollama serve
```

### ChromaDB 初始化失败
```bash
# 删除持久化目录重试
rm -rf data/chroma/
python -m app.main
```

### Vault 路径不对
```bash
# 检查 .env 中的 VAULT_PATH
# 确保路径用 ~ 或绝对路径
```

### Git 推送失败
```bash
# 检查远程仓库配置
git remote -v

# 检查 SSH 密钥
ssh -T git@github.com

# 手动推送
git push -u origin main
```
