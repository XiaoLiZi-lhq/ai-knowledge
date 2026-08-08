# Git 提交规范

## 提交格式

```
<type>: <简短描述>

Timestamp: 自动生成
Auto-committed by AI Knowledge Hub
```

## Type 类型

| 类型 | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: 新增RAG问答API` |
| `fix` | 修复Bug | `fix: 修复ChromaDB初始化失败问题` |
| `refactor` | 重构 | `refactor: 重构LLM调用层` |
| `docs` | 文档 | `docs: 更新README部署说明` |
| `config` | 配置 | `config: 添加微信白名单配置` |
| `test` | 测试 | `test: 新增RAG管道单元测试` |
| `chore` | 杂项/备份 | `chore: auto backup update` |

## 使用方式

```bash
# 手动提交（推荐）
./scripts/git-commit.sh "feat: 新增GitHub热点收集功能"

# 自动备份提交（无特定消息时）
./scripts/git-commit.sh

# 在代码中调用（Python脚本自动提交）
# 见 app/services/git_service.py
```

## 自动提交时机

1. **每次代码文件修改后** — 开发者手动执行
2. **Obsidian Vault 变更** — Obsidian Git 插件每10分钟自动提交
3. **定时备份** — 可选配置 cron 每日全量备份

## GitHub 仓库配置

```bash
# 首次配置远程仓库
cd ai-knowledge-hub
git remote add origin git@github.com:<username>/ai-knowledge-hub.git

# 验证
git remote -v

# 之后每次提交自动推送
./scripts/git-commit.sh "feat: 初始项目结构"
```
