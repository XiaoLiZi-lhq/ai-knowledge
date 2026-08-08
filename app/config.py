"""
AI Knowledge Hub - 配置管理
从环境变量加载所有配置，单一入口
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """全局配置 - 从 .env 加载"""

    # --- API ---
    API_KEY: str = os.getenv("API_KEY", "change-me")

    # --- Ollama 本地模型 ---
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    # --- DeepSeek API（备用） ---
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # --- Obsidian Vault ---
    VAULT_PATH: str = os.getenv("VAULT_PATH", str(Path.home() / "Documents" / "MyVault"))

    # --- GitHub ---
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

    # --- 微信 ---
    WECHAT_WHITE_LIST: list = [
        wxid.strip() for wxid in os.getenv("WECHAT_WHITE_LIST", "").split(",") if wxid.strip()
    ]

    # --- 存储 ---
    CHROMA_PERSIST_PATH: str = os.getenv("CHROMA_PERSIST_PATH", "./data/chroma")
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "./data/sqlite/knowledge.db")

    # --- RAG 参数 ---
    RAG_TOP_K: int = 5
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50

    @property
    def vault_path_obj(self) -> Path:
        """Vault Path 对象"""
        return Path(os.path.expanduser(self.VAULT_PATH))


settings = Settings()
