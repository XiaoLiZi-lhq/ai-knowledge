"""
AI Knowledge Hub - 文档分块器
将 Markdown 笔记按语义边界分块
"""

from dataclasses import dataclass
from app.config import settings


@dataclass
class Document:
    """分块后的文档片段"""
    content: str
    metadata: dict


class MarkdownChunker:
    """Markdown 文档分块 - 按标题层级 + 滑动窗口"""

    def __init__(
        self,
        chunk_size: int = settings.RAG_CHUNK_SIZE,
        overlap: int = settings.RAG_CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_markdown(self, text: str, source_path: str, title: str = "", tags: list = None) -> list[Document]:
        """
        分块策略：
        1. 先按 ## 和 ### 标题拆分为大段
        2. 每段如果超过 chunk_size，用滑动窗口进一步切
        3. 保留 frontmatter 元数据
        """
        # 提取 frontmatter
        frontmatter_tags = []
        clean_text = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm = parts[1]
                clean_text = parts[2]
                # 简单提取 tags
                for line in fm.split("\n"):
                    if line.strip().startswith("tags:"):
                        tag_part = line.split(":", 1)[1].strip()
                        if tag_part.startswith("["):
                            frontmatter_tags = [
                                t.strip().strip('"\'')
                                for t in tag_part.strip("[]").split(",")
                                if t.strip()
                            ]

        all_tags = list(set((tags or []) + frontmatter_tags))

        # 按标题分段
        sections = self._split_by_headers(clean_text)

        # 对每段做滑动窗口分块
        documents = []
        for section_title, section_content in sections:
            if len(section_content) <= self.chunk_size:
                documents.append(Document(
                    content=f"{section_title}\n{section_content}".strip(),
                    metadata={
                        "source_path": source_path,
                        "title": title or source_path,
                        "section": section_title.strip("# ").strip(),
                        "tags": ",".join(all_tags),
                    },
                ))
            else:
                for chunk in self._sliding_window(section_content):
                    documents.append(Document(
                        content=f"{section_title}\n{chunk}".strip(),
                        metadata={
                            "source_path": source_path,
                            "title": title or source_path,
                            "section": section_title.strip("# ").strip(),
                            "tags": ",".join(all_tags),
                        },
                    ))

        return documents

    def _split_by_headers(self, text: str) -> list[tuple[str, str]]:
        """按 ## 和 ### 标题拆分"""
        sections = []
        current_title = ""
        current_content = []

        for line in text.split("\n"):
            if line.startswith("## ") or line.startswith("### "):
                if current_content:
                    sections.append((current_title, "\n".join(current_content)))
                current_title = line
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections.append((current_title, "\n".join(current_content)))

        return sections if sections else [("", text)]

    def _sliding_window(self, text: str) -> list[str]:
        """滑动窗口切分长文本"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            # 尽量在句号/换行处断开
            if end < len(text):
                for sep in ["\n\n", "\n", "。", ". ", " "]:
                    last_sep = chunk.rfind(sep)
                    if last_sep > self.chunk_size * 0.5:
                        end = start + last_sep + len(sep)
                        chunk = text[start:end]
                        break
            chunks.append(chunk.strip())
            start = end - self.overlap
            if start >= len(text):
                break
        return chunks


chunker = MarkdownChunker()
