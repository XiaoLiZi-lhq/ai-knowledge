"""
AI Knowledge Hub - LLM 调用层
统一封装 Ollama 本地模型和 DeepSeek API，支持自动降级
嵌入层：Ollama nomic-embed-text → sentence-transformers → 本地哈希向量
"""

import os
import httpx
from openai import OpenAI
from typing import Generator, Optional
from app.config import settings


class LLMService:
    """LLM 服务 - Ollama 优先，DeepSeek 降级"""

    def __init__(self):
        self._ollama_client: Optional[OpenAI] = None
        self._deepseek_client: Optional[OpenAI] = None
        self._ollama_available = False
        self._st_model = None

    @property
    def ollama_client(self) -> OpenAI:
        if self._ollama_client is None:
            self._ollama_client = OpenAI(
                base_url=settings.OLLAMA_BASE_URL,
                api_key="ollama",
            )
        return self._ollama_client

    @property
    def deepseek_client(self) -> OpenAI:
        if self._deepseek_client is None:
            self._deepseek_client = OpenAI(
                base_url=settings.DEEPSEEK_BASE_URL,
                api_key=settings.DEEPSEEK_API_KEY,
            )
        return self._deepseek_client

    def check_ollama(self) -> bool:
        """检查 Ollama 是否可用"""
        try:
            base = settings.OLLAMA_BASE_URL.replace("/v1", "")
            resp = httpx.get(f"{base}/api/tags", timeout=5)
            self._ollama_available = resp.status_code == 200
            return self._ollama_available
        except Exception:
            self._ollama_available = False
            return False

    def _get_ollama_base(self) -> str:
        """获取 Ollama 原生 API base URL"""
        return settings.OLLAMA_BASE_URL.replace("/v1", "")

    def chat(
        self,
        messages: list[dict],
        use_local: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        同步对话 - 返回完整文本
        Ollama 原生 API 优先，降级 DeepSeek
        """
        if use_local and self.check_ollama():
            try:
                base = self._get_ollama_base()
                resp = httpx.post(
                    f"{base}/api/chat",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "messages": messages,
                        "stream": False,
                        "think": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                    timeout=120,
                )
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                if content:
                    return content
            except Exception:
                pass  # 降级

        # 降级到 DeepSeek
        if settings.DEEPSEEK_API_KEY:
            response = self.deepseek_client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content

        raise RuntimeError("所有 LLM 后端均不可用（Ollama 和 DeepSeek）")

    def chat_stream(
        self,
        messages: list[dict],
        use_local: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Generator[str, None, None]:
        """流式对话 - 逐 token 返回"""
        if use_local and self.check_ollama():
            try:
                base = self._get_ollama_base()
                with httpx.stream(
                    "POST",
                    f"{base}/api/chat",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "messages": messages,
                        "stream": True,
                        "think": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                    timeout=120,
                ) as resp:
                    for line in resp.iter_lines():
                        if line:
                            import json
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                return
            except Exception:
                pass

        # DeepSeek 流式
        if settings.DEEPSEEK_API_KEY:
            stream = self.deepseek_client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return

        raise RuntimeError("所有 LLM 后端均不可用")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        生成文本嵌入向量
        三级降级策略：
        1. Ollama nomic-embed-text（最佳，需本地有模型）
        2. sentence-transformers BAAI/bge-small-zh-v1.5（需可下载模型）
        3. 本地哈希向量引擎（零依赖兜底）
        """
        # 第一优先级：Ollama embedding
        if self.check_ollama():
            try:
                base = self._get_ollama_base()
                # 先检查 embedding 模型是否已安装
                tags_resp = httpx.get(f"{base}/api/tags", timeout=5)
                installed_models = [
                    m.get("name", "") for m in tags_resp.json().get("models", [])
                ]
                embed_model = settings.OLLAMA_EMBED_MODEL

                if any(embed_model in m for m in installed_models):
                    embeddings = []
                    for text in texts:
                        resp = httpx.post(
                            f"{base}/api/embeddings",
                            json={
                                "model": embed_model,
                                "prompt": text,
                            },
                            timeout=30,
                        )
                        data = resp.json()
                        if "embedding" in data:
                            embeddings.append(data["embedding"])
                    if embeddings:
                        return embeddings
            except Exception:
                pass

        # 第二优先级：sentence-transformers
        try:
            return self._embed_with_st(texts)
        except Exception:
            pass

        # 第三优先级：本地哈希向量（零依赖兜底）
        return self._embed_with_local(texts)

    def _embed_with_st(self, texts: list[str]) -> list[list[float]]:
        """用 sentence-transformers 生成嵌入"""
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer("BAAI/bge-small-zh-v1.5")

        embeddings = self._st_model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def _embed_with_local(self, texts: list[str]) -> list[list[float]]:
        """本地哈希向量引擎 - 零外部依赖"""
        from app.core.local_embedding import local_embedder
        return local_embedder.embed(texts)


llm_service = LLMService()
