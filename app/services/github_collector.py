"""
AI Knowledge Hub - GitHub Trending 收集器
每日自动抓取 GitHub 热门项目，AI 生成摘要，写入 Vault
"""

import httpx
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from app.config import settings
from app.core.llm import llm_service
from app.core.rag import rag
import sqlite3
import json


class GitHubCollector:
    """GitHub Trending 收集器"""

    TRENDING_URL = "https://github.com/trending"

    def __init__(self):
        self._db_path = settings.SQLITE_PATH
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化 SQLite 缓存表"""
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS github_cache (
                id INTEGER PRIMARY KEY,
                repo_name TEXT NOT NULL,
                url TEXT NOT NULL,
                description TEXT,
                stars INTEGER DEFAULT 0,
                language TEXT,
                topics TEXT,
                fetched_date DATE NOT NULL,
                summary TEXT,
                tags TEXT,
                UNIQUE(url, fetched_date)
            )
        """)
        conn.commit()
        conn.close()

    async def fetch_trending(
        self,
        language: str = "",
        since: str = "daily",
    ) -> list[dict]:
        """
        抓取 GitHub Trending
        language: python, typescript 等（空字符串=全部）
        since: daily, weekly, monthly
        """
        url = f"{self.TRENDING_URL}/{language}".rstrip("/")
        params = {"since": since}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("article.Box-row")

        projects = []
        for item in items[:20]:  # 最多取20个
            # 仓库名
            name_elem = item.select_one("h2 a")
            if not name_elem:
                continue
            repo_name = name_elem.get("href", "").strip("/")

            # 描述
            desc_elem = item.select_one("p")
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # 语言
            lang_elem = item.select_one("[itemprop='programmingLanguage']")
            lang = lang_elem.get_text(strip=True) if lang_elem else language or "Unknown"

            # Star 数
            stars_elem = item.select_all("a.Link")
            stars = 0
            for s in stars_elem:
                text = s.get_text(strip=True).replace(",", "")
                if text.isdigit():
                    stars = int(text)
                    break

            projects.append({
                "repo_name": repo_name,
                "url": f"https://github.com/{repo_name}",
                "description": description,
                "stars": stars,
                "language": lang,
            })

        return projects

    async def fetch_readme_summary(self, repo_name: str) -> str:
        """获取 README 前 2000 字"""
        readme_url = f"https://raw.githubusercontent.com/{repo_name}/main/README.md"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(readme_url, follow_redirects=True)
                if resp.status_code == 404:
                    readme_url = f"https://raw.githubusercontent.com/{repo_name}/master/README.md"
                    resp = await client.get(readme_url, follow_redirects=True)
                if resp.status_code == 200:
                    return resp.text[:2000]
        except Exception:
            pass
        return ""

    def generate_summary(self, project: dict, readme: str) -> dict:
        """用 LLM 生成项目摘要和标签"""
        prompt = f"""分析以下 GitHub 项目，生成简洁的中文摘要和标签。

项目名：{project['repo_name']}
描述：{project['description']}
Star：{project['stars']}
README（前2000字）：
{readme}

请输出 JSON 格式：
{{"summary": "3句话摘要（项目是什么、核心功能、为什么值得关注）", "tags": ["标签1", "标签2"]}}

只输出 JSON，不要其他文字。"""

        try:
            result = llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            # 尝试解析 JSON
            result = result.strip().strip("```json").strip("```").strip()
            data = json.loads(result)
            return data
        except Exception:
            return {
                "summary": project["description"][:200] if project["description"] else "暂无描述",
                "tags": ["未分类"],
            }

    async def collect_daily(self, languages: list[str] = None) -> dict:
        """
        每日收集流程：
        1. 抓取 GitHub Trending
        2. AI 生成摘要
        3. 写入 Obsidian Vault
        4. 向量化入 ChromaDB
        5. 返回结果摘要
        """
        if languages is None:
            languages = ["python", "typescript"]

        today = date.today().isoformat()
        all_projects = []

        for lang in languages:
            projects = await self.fetch_trending(language=lang, since="daily")
            for p in projects:
                p["language"] = lang
                all_projects.append(p)

        # 去重
        seen = set()
        unique = []
        for p in all_projects:
            if p["repo_name"] not in seen:
                seen.add(p["repo_name"])
                unique.append(p)

        # AI 摘要
        results = []
        for project in unique[:15]:  # 最多处理15个
            readme = await self.fetch_readme_summary(project["repo_name"])
            summary_data = self.generate_summary(project, readme)
            project["summary"] = summary_data["summary"]
            project["tags"] = summary_data["tags"]
            results.append(project)

        # 写入 Markdown
        md_path = self._write_markdown(results, today)

        # 写入 SQLite
        self._save_to_db(results, today)

        # 向量化入 ChromaDB
        self._index_to_chroma(results)

        return {
            "date": today,
            "total": len(results),
            "markdown_path": str(md_path),
            "top_projects": [
                {"name": r["repo_name"], "stars": r["stars"], "summary": r["summary"]}
                for r in results[:5]
            ],
        }

    def _write_markdown(self, projects: list[dict], today: str) -> Path:
        """生成 Markdown 日报写入 Vault"""
        vault = settings.vault_path_obj
        trending_dir = vault / "02-Resources" / "GitHub-Trending"
        trending_dir.mkdir(parents=True, exist_ok=True)

        md_path = trending_dir / f"{today}.md"

        lines = [
            f"---",
            f"date: {today}",
            f"type: github-trending",
            f"tags: [GitHub, 热点追踪]",
            f"---",
            f"",
            f"# GitHub Trending 日报 - {today}",
            f"",
        ]

        # 按语言分组
        by_lang = {}
        for p in projects:
            lang = p.get("language", "Other")
            if lang not in by_lang:
                by_lang[lang] = []
            by_lang[lang].append(p)

        for lang, items in by_lang.items():
            lines.append(f"## {lang} 热门项目")
            lines.append("")
            for i, p in enumerate(items, 1):
                tags_str = " ".join([f"#{t}" for t in p.get("tags", [])])
                lines.append(f"### {i}. {p['repo_name']}")
                lines.append(f"Stars: {p['stars']} | Language: {p['language']}")
                lines.append(f"Tags: {tags_str}")
                lines.append(f"")
                lines.append(f"{p['summary']}")
                lines.append(f"")
                lines.append(f"[GitHub链接]({p['url']})")
                lines.append(f"")

        lines.append("---")
        lines.append(f"*本日报由 AI Knowledge Hub 自动生成于 {datetime.now().strftime('%H:%M')}*")

        md_path.write_text("\n".join(lines), encoding="utf-8")
        return md_path

    def _save_to_db(self, projects: list[dict], today: str):
        """保存到 SQLite"""
        conn = sqlite3.connect(self._db_path)
        for p in projects:
            conn.execute(
                """INSERT OR REPLACE INTO github_cache
                (repo_name, url, description, stars, language, topics, fetched_date, summary, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    p["repo_name"], p["url"], p.get("description", ""),
                    p.get("stars", 0), p.get("language", ""),
                    json.dumps(p.get("topics", []), ensure_ascii=False),
                    today, p.get("summary", ""),
                    json.dumps(p.get("tags", []), ensure_ascii=False),
                ),
            )
        conn.commit()
        conn.close()

    def _index_to_chroma(self, projects: list[dict]):
        """向量化入 ChromaDB"""
        for p in projects:
            text = f"{p['repo_name']}: {p['summary']}"
            try:
                embedding = llm_service.embed([text])[0]
                rag.github_collection.upsert(
                    ids=[f"gh_{p['repo_name'].replace('/', '_')}_{date.today()}"],
                    embeddings=[embedding],
                    documents=[text],
                    metadatas=[{
                        "repo_name": p["repo_name"],
                        "url": p["url"],
                        "stars": p.get("stars", 0),
                        "language": p.get("language", ""),
                        "date": date.today().isoformat(),
                    }],
                )
            except Exception:
                continue

    def get_today(self) -> list[dict]:
        """获取今日热点（从 SQLite）"""
        today = date.today().isoformat()
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM github_cache WHERE fetched_date = ? ORDER BY stars DESC",
            (today,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


github_collector = GitHubCollector()
