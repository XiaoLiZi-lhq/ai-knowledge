"""
AI Knowledge Hub - LLM 调用层
统一封装 Ollama 本地模型和 DeepSeek API，支持自动降级
"""

from openai import OpenAI
from typing import Generator, Optional
from app.config import settings


class LLMService:
    """LLM 服务 - Ollama 优先，DeepSeek 降级"""

    def __init__(self):
        self._ollama_client: Optional[OpenAI] = None
        self._deepseek_client: Optional[OpenAI] = None
        self._ollama_available = False

    @property
    def ollama_client(self) -> OpenAI:
        if self._ollama_client is None:
            self._ollama_client = OpenAI(
                base_url=settings.OLLAMA_BASE_URL,
                api_key="ollama",  # Ollama 不校验 key，但字段必须有
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
            self.ollama_client.models.list()
            self._ollama_available = True
            return True
        except Exception:
            self._ollama_available = False
            return False

    def chat(
        self,
        messages: list[dict],
        use_local: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        同步对话 - 返回完整文本
        Ollama 优先，不可用时降级 DeepSeek
        """
        if use_local and self.check_ollama():
            try:
                response = self.ollama_client.chat.completions.create(
                    model=settings.OLLAMA_MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
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
        """
        流式对话 - 逐 token 返回
        适合实时输出场景（Obsidian 面板、微信回复）
        """
        backend = "ollama" if (use_local and self.check_ollama()) else "deepseek"

        if backend == "ollama":
            try:
                stream = self.ollama_client.chat.completions.create(
                    model=settings.OLLAMA_MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except Exception:
                pass  # 降级

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
        """生成文本嵌入向量（仅用 Ollama 本地）"""
        if not self.check_ollama():
            raise RuntimeError("Ollama 不可用，无法生成嵌入向量")

        embeddings = []
        for text in texts:
            response = self.ollama_client.embeddings.create(
                model=settings.OLLAMA_EMBED_MODEL,
                input=text,
            )
            embeddings.append(response.data[0].embedding)
        return embeddings


# 全局单例
llm_service = LLMService()
