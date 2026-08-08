"""
AI Knowledge Hub - 笔记自动整理服务
AI 自动打标、分类建议、双链关联推荐
"""

from pathlib import Path
from app.config import settings
from app.core.llm import llm_service
from app.core.rag import rag
import json
import frontmatter


class NoteOrganizer:
    """笔记自动整理"""

    def organize(self, note_path: str) -> dict:
        """
        分析单篇笔记，输出：
        - 推荐标签
        - 分类建议
        - 双链关联推荐
        - 摘要
        """
        path = Path(note_path)
        if not path.exists():
            return {"error": f"文件不存在: {note_path}"}

        text = path.read_text(encoding="utf-8")

        # 解析 frontmatter
        try:
            post = frontmatter.loads(text)
            content = post.content
            existing_tags = post.get("tags", [])
        except Exception:
            content = text
            existing_tags = []

        # RAG 检索相关笔记
        related = rag.retrieve(content[:500], top_k=5)
        related_notes = [
            {"title": r["metadata"].get("title", ""), "path": r["metadata"].get("source_path", "")}
            for r in related
            if r["metadata"].get("source_path", "") != str(path)
        ]

        # LLM 分析
        related_text = "\n".join([f"- [[{n['title']}]]" for n in related_notes[:5]])

        prompt = f"""分析以下笔记内容，输出整理建议。

笔记内容（前1000字）：
{content[:1000]}

已有标签：{existing_tags}
相关笔记：{related_text or "无"}

输出 JSON：
{{
  "suggested_tags": ["标签1", "标签2", "标签3"],
  "category": "建议分类（如 AI-ML/课程笔记/编程实践/工具技巧）",
  "summary": "一句话摘要",
  "suggested_links": ["相关笔记标题1", "相关笔记标题2"],
  "quality_score": 8,
  "improvement_suggestions": ["改进建议1", "改进建议2"]
}}

只输出 JSON。"""

        result = llm_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )

        try:
            result = result.strip().strip("```json").strip("```").strip()
            suggestions = json.loads(result)
            suggestions["related_notes"] = related_notes[:5]
            return suggestions
        except Exception:
            return {"error": "分析失败", "raw": result[:300]}

    def batch_organize(self, folder: str = "00-Inbox") -> dict:
        """
        批量整理指定文件夹的笔记
        默认处理 Inbox 中的待整理笔记
        """
        vault = settings.vault_path_obj
        target = vault / folder

        if not target.exists():
            return {"error": f"文件夹不存在: {folder}"}

        results = []
        for md in target.glob("*.md"):
            suggestions = self.organize(str(md))
            results.append({"file": md.name, "suggestions": suggestions})

        return {"total": len(results), "results": results}

    def auto_tag(self, note_path: str, apply: bool = False) -> dict:
        """
        自动打标签
        apply=True 时直接写入文件 frontmatter
        """
        path = Path(note_path)
        suggestions = self.organize(note_path)

        if "error" in suggestions:
            return suggestions

        tags = suggestions.get("suggested_tags", [])

        if apply:
            text = path.read_text(encoding="utf-8")
            try:
                post = frontmatter.loads(text)
                existing = post.get("tags", [])
                merged = list(set(existing + tags))
                post["tags"] = merged
                path.write_text(frontmatter.dumps(post), encoding="utf-8")
                return {"applied": True, "tags": merged, "added": list(set(tags) - set(existing))}
            except Exception as e:
                return {"applied": False, "error": str(e)}

        return {"suggested_tags": tags}


note_organizer = NoteOrganizer()
