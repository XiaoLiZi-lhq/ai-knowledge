"""
AI Knowledge Hub - RAG 管道
自研三层漏斗检索：向量搜索 → BM25 重排 → 业务过滤
"""

import hashlib
import math

import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Optional
from app.config import settings
from app.core.llm import llm_service
from app.core.chunker import chunker


class RAGPipeline:
    """RAG 管道 - 检索增强生成"""

    def __init__(self):
        self._client: Optional[chromadb.PersistentClient] = None
        self._notes_collection = None
        self._github_collection = None

    @property
    def client(self) -> chromadb.PersistentClient:
        if self._client is None:
            import os
            os.makedirs(settings.CHROMA_PERSIST_PATH, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_PATH,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def notes_collection(self):
        if self._notes_collection is None:
            self._notes_collection = self.client.get_or_create_collection(
                name="notes",
                metadata={"description": "Obsidian Vault 笔记向量"},
            )
        return self._notes_collection

    @property
    def github_collection(self):
        if self._github_collection is None:
            self._github_collection = self.client.get_or_create_collection(
                name="github_trending",
                metadata={"description": "GitHub Trending 项目向量"},
            )
        return self._github_collection

    def index_vault(self, force: bool = False) -> int:
        """
        索引整个 Obsidian Vault
        返回索引的文档块数量
        """
        vault_path = settings.vault_path_obj
        if not vault_path.exists():
            raise FileNotFoundError(f"Vault 路径不存在: {vault_path}")

        # 获取已索引的文件
        indexed = set()
        if not force:
            existing = self.notes_collection.get()
            for meta in existing.get("metadatas", []):
                if meta and "source_path" in meta:
                    indexed.add(meta["source_path"])

        count = 0
        md_files = list(vault_path.rglob("*.md"))

        # 排除模板、配置目录，以及代码项目目录（node_modules 等巨型 changelog 会撑爆 embedding 上下文/超时降级，导致维度混仓）
        exclude_dirs = {".obsidian", "03-Templates", "99-Archive", "node_modules", "redis-learn"}
        exclude_names = {"CHANGELOG.md", "CHANGES.md", "LICENSE.md", "CODE_OF_CONDUCT.md"}
        md_files = [
            f for f in md_files
            if not any(d in f.parts for d in exclude_dirs)
            and f.name not in exclude_names
        ]

        for md_file in md_files:
            file_key = str(md_file)
            if file_key in indexed and not force:
                continue

            text = md_file.read_text(encoding="utf-8")
            if not text.strip():
                continue

            title = md_file.stem
            docs = chunker.chunk_markdown(text, source_path=file_key, title=title)

            if not docs:
                continue

            # 批量生成嵌入
            try:
                embeddings = llm_service.embed([d.content for d in docs])
            except Exception:
                continue

            # 写入 ChromaDB（ID 用文件路径哈希前缀，防止不同目录同名文件互相覆盖）
            path_hash = hashlib.md5(file_key.encode()).hexdigest()[:8]
            ids = [f"{path_hash}_{i}" for i in range(len(docs))]
            self.notes_collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=[d.content for d in docs],
                metadatas=[d.metadata for d in docs],
            )
            count += len(docs)

        return count

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        三层漏斗检索
        1. 向量搜索 Top-20
        2. BM25 关键词重排序
        3. 返回 Top-K
        """
        # 生成查询向量
        query_embedding = llm_service.embed([query])[0]

        # 第一层：向量搜索 Top-20
        results = self.notes_collection.query(
            query_embeddings=[query_embedding],
            n_results=min(20, top_k * 4),
            include=["documents", "metadatas", "distances"],
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        candidates = []
        for i, doc in enumerate(results["documents"][0]):
            candidates.append({
                "content": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })

        # 第二层：BM25 重排（jieba 分词，基于候选池局部 IDF）
        self._bm25_rerank(query, candidates)
        candidates.sort(key=lambda x: x["bm25_score"] - x["distance"] * 0.3, reverse=True)

        # 第三层：过滤 + 取 Top-K
        filtered = [c for c in candidates if c["distance"] < 1.5]  # 相关性阈值
        return filtered[:top_k]

    def _tokenize(self, text: str) -> list[str]:
        """jieba 搜索引擎模式分词，过滤空白与标点"""
        import jieba
        return [t for t in jieba.cut_for_search(text.lower()) if t.strip()]

    def _bm25_rerank(self, query: str, candidates: list[dict], k1: float = 1.5, b: float = 0.75) -> None:
        """
        对候选池做 BM25 打分（就地写入 bm25_score 字段）
        IDF 从候选池内统计（局部 IDF），适配重排场景的小样本
        """
        query_terms = set(self._tokenize(query))
        if not query_terms or not candidates:
            for c in candidates:
                c["bm25_score"] = 0.0
            return

        doc_tokens = [self._tokenize(c["content"]) for c in candidates]
        N = len(candidates)
        avgdl = sum(len(t) for t in doc_tokens) / N if N else 0.0

        # 候选池内文档频率 → IDF
        df = {}
        for tokens in doc_tokens:
            for term in set(tokens) & query_terms:
                df[term] = df.get(term, 0) + 1

        for c, tokens in zip(candidates, doc_tokens):
            dl = len(tokens)
            score = 0.0
            for term in query_terms:
                if term not in df:
                    continue
                tf = tokens.count(term)
                if tf == 0:
                    continue
                idf = math.log(1 + (N - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avgdl))
            c["bm25_score"] = score

    def _bm25_score(self, query: str, document: str) -> float:
        """单文档 BM25 分数（保留旧签名兼容，内部走 jieba 分词）"""
        single = [{"content": document}]
        self._bm25_rerank(query, single)
        return single[0]["bm25_score"]

    def answer(self, query: str, history: list[dict] = None) -> dict:
        """
        完整 RAG 问答
        返回 {answer, sources}
        """
        # 检索相关文档
        retrieved = self.retrieve(query, top_k=settings.RAG_TOP_K)

        if not retrieved:
            return {
                "answer": "知识库中未找到相关内容。请尝试换个问法，或先导入相关笔记。",
                "sources": [],
            }

        # 构建上下文
        context_parts = []
        sources = []
        for i, doc in enumerate(retrieved):
            context_parts.append(f"[{i+1}] {doc['content']}")
            title = doc["metadata"].get("title", "未知")
            path = doc["metadata"].get("source_path", "")
            sources.append({"title": title, "path": path})

        context = "\n\n".join(context_parts)

        # 构建 Prompt
        system_prompt = (
            "你是一个知识库助手。请根据以下检索到的笔记内容回答问题。\n"
            "规则：\n"
            "1. 只基于提供的上下文回答，不要编造\n"
            "2. 如果上下文不足以回答，明确说明\n"
            "3. 回答简洁准确\n"
            "4. 在回答末尾标注信息来源\n\n"
            f"参考笔记：\n{context}"
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-4:])  # 最近4轮对话
        messages.append({"role": "user", "content": query})

        answer = llm_service.chat(messages, temperature=0.3, max_tokens=1500)

        return {"answer": answer, "sources": sources}

    def answer_stream(self, query: str, history: list[dict] = None):
        """流式 RAG 问答 - 生成器"""
        retrieved = self.retrieve(query, top_k=settings.RAG_TOP_K)

        sources = []
        if not retrieved:
            yield "知识库中未找到相关内容。"
            return

        context_parts = []
        for i, doc in enumerate(retrieved):
            context_parts.append(f"[{i+1}] {doc['content']}")
            sources.append({
                "title": doc["metadata"].get("title", "未知"),
                "path": doc["metadata"].get("source_path", ""),
            })

        context = "\n\n".join(context_parts)
        system_prompt = (
            "你是一个知识库助手。请根据以下检索到的笔记内容回答问题。\n"
            "只基于提供的上下文回答，不要编造。回答简洁准确。\n\n"
            f"参考笔记：\n{context}"
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-4:])
        messages.append({"role": "user", "content": query})

        for token in llm_service.chat_stream(messages, temperature=0.3):
            yield token

        # 最后输出来源
        source_text = "\n\n---\n来源：\n"
        for s in sources:
            source_text += f"- [[{s['title']}]]\n"
        yield source_text


rag = RAGPipeline()
