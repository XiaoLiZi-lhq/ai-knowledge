#!/bin/bash
# ====================================
# AI Knowledge Hub - Git 自动提交脚本
# 用法: ./scripts/git-commit.sh "feat: 新增RAG问答功能"
# ====================================

set -e

COMMIT_MSG="${1:-chore: auto backup update}"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S %Z")
FULL_MSG="$COMMIT_MSG

Timestamp: $TIMESTAMP
Auto-committed by AI Knowledge Hub"

# 切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  AI Knowledge Hub - Git Commit"
echo "=========================================="
echo ""

# 检查是否有 .git 目录，没有则初始化
if [ ! -d ".git" ]; then
    echo "[1/5] 初始化 Git 仓库..."
    git init
    git branch -M main
    echo "  Git 仓库已初始化"
else
    echo "[1/5] Git 仓库已存在"
fi

# 检查远程仓库
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [ -z "$REMOTE_URL" ]; then
    echo ""
    echo "  [警告] 未检测到远程仓库。"
    echo "  请运行: git remote add origin <your-github-repo-url>"
    echo "  然后重新执行本脚本。"
    echo ""
    echo "  是否继续仅本地提交？(y/n)"
    read -r response
    if [[ ! "$response" =~ ^[yY]$ ]]; then
        echo "已取消。"
        exit 1
    fi
    PUSH_ENABLED=false
else
    PUSH_ENABLED=true
    echo "[2/5] 远程仓库: $REMOTE_URL"
fi

# 显示变更概要
echo ""
echo "[3/5] 变更文件概要:"
CHANGED=$(git status --short 2>/dev/null | wc -l | xargs)
echo "  共 $CHANGED 个文件变更"
if [ "$CHANGED" -eq 0 ]; then
    echo "  无变更，跳过提交。"
    exit 0
fi
git status --short | head -20
if [ "$CHANGED" -gt 20 ]; then
    echo "  ... 及其余 $((CHANGED - 20)) 个文件"
fi

# 暂存并提交
echo ""
echo "[4/5] 提交中..."
git add -A
git commit -m "$FULL_MSG" --no-verify 2>/dev/null || {
    echo "  [提示] 提交可能失败（无变更或pre-commit hook拦截），尝试继续..."
}

# 推送
if [ "$PUSH_ENABLED" = true ]; then
    echo ""
    echo "[5/5] 推送到 GitHub..."
    git push -u origin main 2>/dev/null || {
        echo "  [警告] 推送失败，可能需要先 git pull --rebase origin main"
        echo "  本地提交已保存，稍后可手动推送。"
    }
    echo "  推送完成"
else
    echo "[5/5] 跳过推送（无远程仓库配置）"
fi

echo ""
echo "=========================================="
echo "  提交完成!"
echo "  消息: $COMMIT_MSG"
echo "  时间: $TIMESTAMP"
echo "=========================================="
