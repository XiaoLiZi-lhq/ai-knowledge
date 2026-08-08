"""
AI Knowledge Hub - 测试套件
验证核心功能正确性
"""

import pytest
from pathlib import Path
from app.config import settings


class TestConfig:
    """配置测试"""

    def test_settings_loaded(self):
        assert settings.OLLAMA_MODEL == "qwen3.5:9b"
        assert settings.OLLAMA_EMBED_MODEL == "nomic-embed-text"

    def test_vault_path_expandable(self):
        path = settings.vault_path_obj
        assert "~" not in str(path)  # 应已展开


class TestChunker:
    """文档分块测试"""

    def test_split_by_headers(self):
        from app.core.chunker import MarkdownChunker
        chunker = MarkdownChunker()

        text = """## 标题A
内容A

## 标题B
内容B"""

        sections = chunker._split_by_headers(text)
        assert len(sections) == 2

    def test_sliding_window(self):
        from app.core.chunker import MarkdownChunker
        chunker = MarkdownChunker(chunk_size=100, overlap=20)

        long_text = "这是一段很长的文字。" * 50
        chunks = chunker._sliding_window(long_text)
        assert len(chunks) > 1

    def test_chunk_markdown_with_frontmatter(self):
        from app.core.chunker import MarkdownChunker, Document
        chunker = MarkdownChunker()

        text = """---
tags: ["AI", "test"]
---

# 测试笔记

## 概念
这是测试内容。"""

        docs = chunker.chunk_markdown(text, source_path="test.md", title="测试笔记")
        assert len(docs) > 0
        assert "AI" in docs[0].metadata.get("tags", "") or "test" in docs[0].metadata.get("tags", "")


class TestWeChatRouter:
    """微信路由测试"""

    def test_help_command(self):
        from app.integrations.wechat_bridge import WeChatRouter
        router = WeChatRouter()
        reply = router.handle_message("/help", sender="test_user")
        assert "指令" in reply

    def test_unauthorized(self):
        from app.integrations.wechat_bridge import WeChatRouter
        router = WeChatRouter()
        # 白名单模式时非白名单用户应被拒
        settings.WECHAT_WHITE_LIST = ["allowed_user"]
        reply = router.handle_message("hello", sender="blocked_user")
        assert "权限" in reply
        settings.WECHAT_WHITE_LIST = []  # 恢复

    def test_add_command(self):
        from app.integrations.wechat_bridge import WeChatRouter
        router = WeChatRouter()
        settings.WECHAT_WHITE_LIST = ["test_user"]
        reply = router.handle_message("/add 测试灵感", sender="test_user")
        assert "已记录" in reply or "Inbox" in reply
        settings.WECHAT_WHITE_LIST = []


class TestQuizGenerator:
    """出题引擎测试"""

    def test_quiz_structure(self):
        from app.services.ai_tutor import QuizGenerator
        gen = QuizGenerator()
        # 不依赖 LLM 的结构测试
        assert hasattr(gen, "generate")
        assert hasattr(gen, "submit")

    def test_submit_scoring(self):
        from app.services.ai_tutor import QuizGenerator
        gen = QuizGenerator()
        answers = [
            {"question": "Q1", "user_answer": "A", "correct_answer": "A"},
            {"question": "Q2", "user_answer": "B", "correct_answer": "C"},
        ]
        result = gen.submit(answers)
        assert result["score"] == 50
        assert result["correct"] == 1


class TestGapScanner:
    """盲区扫描测试"""

    def test_knowledge_tree_exists(self):
        from app.services.ai_tutor import DEFAULT_KNOWLEDGE_TREE
        assert "深度学习" in DEFAULT_KNOWLEDGE_TREE
        assert "Transformer" in DEFAULT_KNOWLEDGE_TREE["深度学习"]


class TestGitHubCollector:
    """GitHub 收集器测试"""

    def test_db_init(self):
        from app.services.github_collector import GitHubCollector
        collector = GitHubCollector()
        assert Path(settings.SQLITE_PATH).exists()


class TestRAGPipeline:
    """RAG 管道测试"""

    def test_bm25_score(self):
        from app.core.rag import RAGPipeline
        rag = RAGPipeline()
        score = rag._bm25_score("attention transformer", "attention is all you need transformer")
        assert score > 0

    def test_bm25_empty(self):
        from app.core.rag import RAGPipeline
        rag = RAGPipeline()
        score = rag._bm25_score("test", "")
        assert score == 0.0


class TestGitCommitScript:
    """Git 提交脚本测试"""

    def test_script_exists(self):
        script = Path(__file__).parent.parent / "scripts" / "git-commit.sh"
        assert script.exists()

    def test_script_executable(self):
        import os
        script = Path(__file__).parent.parent / "scripts" / "git-commit.sh"
        assert os.access(script, os.X_OK)


class TestAPPRoutes:
    """API 路由测试"""

    def test_health_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "ollama" in data

    def test_chat_unauthorized(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.post("/api/v1/chat", json={"query": "test"})
        assert resp.status_code == 401
