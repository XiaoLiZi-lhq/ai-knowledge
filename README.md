# AI Knowledge Hub - 个人AI知识中台

以 Obsidian 为底座，集成 Ollama 本地大模型，支持 GitHub 热点收集、微信双向对话、AI 导师学习辅助。

## 快速开始

```bash
# 1. 克隆仓库
git clone <your-repo-url> ai-knowledge-hub
cd ai-knowledge-hub

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key 和路径

# 5. 确保 Ollama 运行
OLLAMA_ORIGINS="*" ollama serve &
ollama pull qwen3.5:9b
ollama pull nomic-embed-text

# 6. 初始化 Obsidian Vault 结构
python scripts/init_vault.py --path ~/Documents/MyVault

# 7. 启动服务
python -m app.main
```

## 项目结构

```
ai-knowledge-hub/
├── app/                    # 主应用
│   ├── main.py            # FastAPI 入口
│   ├── api/               # API 路由
│   ├── core/              # 核心逻辑（RAG/LLM/嵌入）
│   ├── services/          # 业务服务
│   └── integrations/      # 微信/飞书集成
├── config/                # 配置
├── data/                  # 运行时数据
├── scripts/               # 脚本
└── tests/                 # 测试
```

## 核心功能

- RAG 知识库问答（Ollama 本地，DeepSeek 备用）
- GitHub Trending 每日自动收集
- 微信双向对话（指令系统）
- AI 导师（出题/盲区扫描/学习计划）
- Obsidian Vault 自动整理（打标/分类/双链）
- Git 自动备份到 GitHub

## 提交规范

每次代码改动通过 `scripts/git-commit.sh` 提交，自动附带规范的提交说明。
