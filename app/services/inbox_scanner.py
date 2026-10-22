"""
AI Knowledge Hub - 桌面投递箱扫描服务

扫描 ~/Desktop/LearningInbox/ 下的 .md 文件，
解析 frontmatter → MD5 去重 → 导入 Vault → 归档原文件 → 记录学习行为。
"""

import hashlib
import os
import re
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.config import settings


class InboxScanner:
    """桌面投递箱扫描 + 学习行为分析引擎"""

    # Vault 目标目录
    VAULT_LEARNING_DIR = "05-Learning"
    # 已处理原文件归档目录
    PROCESSED_DIR = "data/inbox-processed"

    def __init__(self):
        self.inbox = settings.inbox_path_obj
        self.vault = settings.vault_path_obj
        self.db_path = settings.SQLITE_PATH
        self.processed_dir = Path(self.PROCESSED_DIR)
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保需要的目录都存在"""
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        (self.vault / self.VAULT_LEARNING_DIR).mkdir(parents=True, exist_ok=True)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    # ================================================================
    # 扫描
    # ================================================================

    def scan_inbox(self) -> list[dict]:
        """扫描投递箱，返回文件信息列表"""
        results = []
        if not self.inbox.exists():
            return results

        for md_file in sorted(self.inbox.glob("*.md")):
            # README.md 不算投递内容
            if md_file.name.lower() == "readme.md":
                continue
            info = self._analyze_file(md_file)
            if info:
                results.append(info)

        return results

    def _analyze_file(self, md_file: Path) -> Optional[dict]:
        """分析单个文件，解析 frontmatter + 正文，计算 hash"""
        try:
            raw = md_file.read_text(encoding="utf-8")
        except Exception:
            return None

        if not raw.strip():
            return None

        # 解析 frontmatter
        meta, body = self._parse_frontmatter(raw, md_file)

        # 整个文件的 MD5（用于去重）
        content_hash = hashlib.md5(raw.encode("utf-8")).hexdigest()

        # 预览
        preview = body[:200].replace("\n", " ").strip()

        return {
            "file_path": str(md_file),
            "file_name": md_file.name,
            "title": meta["title"],
            "tags": meta["tags"],
            "source": meta["source"],
            "learn_date": meta["date"],
            "body": body,
            "raw_content": raw,
            "content_hash": content_hash,
            "preview": preview,
            "mtime": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat(),
            "size": md_file.stat().st_size,
        }

    def _parse_frontmatter(self, raw: str, md_file: Path) -> tuple[dict, str]:
        """
        解析 frontmatter，返回 (meta, body)。
        无 frontmatter 时用文件名/修改时间兜底。
        """
        meta = {
            "title": md_file.stem,
            "tags": ["inbox"],
            "source": "manual",
            "date": datetime.fromtimestamp(md_file.stat().st_mtime).strftime("%Y-%m-%d"),
        }
        body = raw

        # 尝试匹配 --- 开头的 frontmatter
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", raw, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            body = fm_match.group(2).strip()

            # 解析简单 key: value 和 key: [a, b, c]
            for line in fm_text.split("\n"):
                line = line.strip()
                if ":" not in line:
                    continue
                key, _, val = line.partition(":")
                key = key.strip().lower()
                val = val.strip()

                if key == "title":
                    meta["title"] = val
                elif key == "source":
                    meta["source"] = val
                elif key == "date":
                    # 只取日期部分 YYYY-MM-DD
                    meta["date"] = val[:10] if val else meta["date"]
                elif key == "tags":
                    # [a, b, c] 或 a, b, c
                    tags = re.sub(r"[\[\]]", "", val)
                    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                    if tag_list:
                        meta["tags"] = tag_list

        return meta, body

    # ================================================================
    # 同步导入
    # ================================================================

    def sync(self, force: bool = False) -> dict:
        """全量扫描导入，返回统计报告"""
        start = datetime.now()
        files = self.scan_inbox()

        stats = {
            "scanned": len(files),
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "details": [],
        }

        already_synced = set() if force else self._load_synced_hashes()

        for f in files:
            try:
                if f["content_hash"] in already_synced:
                    stats["skipped"] += 1
                    stats["details"].append({
                        "file": f["file_name"],
                        "title": f["title"],
                        "status": "skipped",
                    })
                    continue

                vault_path = self._import_to_vault(f)
                self._archive_original(f)
                self._log_to_db(f, vault_path)

                already_synced.add(f["content_hash"])
                stats["imported"] += 1
                stats["details"].append({
                    "file": f["file_name"],
                    "title": f["title"],
                    "source": f["source"],
                    "tags": f["tags"],
                    "status": "imported",
                    "vault_path": str(vault_path),
                })
            except Exception as e:
                stats["errors"] += 1
                stats["details"].append({
                    "file": f["file_name"],
                    "status": "error",
                    "error": str(e),
                })

        stats["duration_seconds"] = round((datetime.now() - start).total_seconds(), 2)
        stats["synced_at"] = datetime.now().isoformat()
        return stats

    def _import_to_vault(self, file_info: dict) -> Path:
        """导入到 Vault/05-Learning，文件名用 title 做安全处理"""
        safe_title = re.sub(r'[\\/:*?"<>|]', "-", file_info["title"]).strip()
        if not safe_title:
            safe_title = file_info["file_name"].replace(".md", "")

        target_path = self.vault / self.VAULT_LEARNING_DIR / f"{safe_title}.md"

        # 重名时加后缀
        counter = 1
        while target_path.exists():
            target_path = self.vault / self.VAULT_LEARNING_DIR / f"{safe_title}-{counter}.md"
            counter += 1

        # 构建带 Knowledge Hub frontmatter 的完整内容
        fm = self._build_frontmatter(file_info)
        full_content = f"---\n{fm}---\n\n# {file_info['title']}\n\n{file_info['body']}\n"
        target_path.write_text(full_content, encoding="utf-8")

        return target_path

    def _build_frontmatter(self, file_info: dict) -> str:
        """构建 Knowledge Hub 格式的 frontmatter"""
        tags_yaml = "\n".join(f"  - {t}" for t in file_info["tags"])
        return (
            f"source: inbox\n"
            f"original_source: {file_info['source']}\n"
            f"learn_date: {file_info['learn_date']}\n"
            f"imported_at: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"content_hash: {file_info['content_hash']}\n"
            f"tags:\n{tags_yaml}\n"
        )

    def _archive_original(self, file_info: dict):
        """把原文件归档到 data/inbox-processed/，加时间戳"""
        src = Path(file_info["file_path"])
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_name = f"{timestamp}-{src.name}"
        dest = self.processed_dir / archive_name
        shutil.move(str(src), str(dest))

    # ================================================================
    # SQLite 记录
    # ================================================================

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inbox_import_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                title TEXT,
                source TEXT,
                vault_path TEXT,
                imported_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learning_behavior (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT NOT NULL,
                learn_date TEXT NOT NULL,
                title TEXT,
                source TEXT,
                tag TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.commit()
        return conn

    def _log_to_db(self, file_info: dict, vault_path: Path):
        """记录到 inbox_import_log + learning_behavior（每个 tag 一行）"""
        conn = self._get_conn()
        cur = conn.cursor()

        # import_log
        cur.execute(
            """INSERT OR REPLACE INTO inbox_import_log
               (content_hash, file_name, title, source, vault_path)
               VALUES (?, ?, ?, ?, ?)""",
            (
                file_info["content_hash"],
                file_info["file_name"],
                file_info["title"],
                file_info["source"],
                str(vault_path),
            ),
        )

        # learning_behavior：每个 tag 一行，方便按 tag 统计
        for tag in file_info["tags"]:
            cur.execute(
                """INSERT INTO learning_behavior
                   (content_hash, learn_date, title, source, tag)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    file_info["content_hash"],
                    file_info["learn_date"],
                    file_info["title"],
                    file_info["source"],
                    tag,
                ),
            )

        # learning_log（兼容既有表）
        cur.execute(
            """INSERT INTO learning_log (date, activity, topic, score)
               VALUES (?, ?, ?, ?)""",
            (
                file_info["learn_date"],
                f"投递箱导入-{file_info['source']}",
                file_info["title"],
                None,
            ),
        )

        conn.commit()
        conn.close()

    def _load_synced_hashes(self) -> set[str]:
        """加载已导入的 content_hash 集合"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT content_hash FROM inbox_import_log")
        hashes = {row[0] for row in cur.fetchall()}
        conn.close()
        return hashes

    # ================================================================
    # 预览
    # ================================================================

    def preview(self) -> dict:
        """预览待导入，不实际操作"""
        files = self.scan_inbox()
        already = self._load_synced_hashes()

        return {
            "total_files": len(files),
            "already_synced": sum(1 for f in files if f["content_hash"] in already),
            "pending": sum(1 for f in files if f["content_hash"] not in already),
            "files": [
                {
                    "file_name": f["file_name"],
                    "title": f["title"],
                    "tags": f["tags"],
                    "source": f["source"],
                    "learn_date": f["learn_date"],
                    "size": f["size"],
                    "preview": f["preview"],
                    "already_synced": f["content_hash"] in already,
                }
                for f in files
            ],
        }

    # ================================================================
    # 学习行为统计
    # ================================================================

    def learning_stats(self, days: int = 30) -> dict:
        """
        学习行为统计，返回：
        - total_notes: 总笔记数
        - total_tags: 不同标签数
        - total_sources: 不同来源数
        - tag_distribution: 标签分布 [{tag, count}]
        - source_distribution: 来源分布 [{source, count}]
        - daily_counts: 每日学习数 [{date, count}]（最近 days 天）
        - streak: 连续学习天数
        - latest_notes: 最近 5 条笔记
        """
        conn = self._get_conn()
        cur = conn.cursor()

        # 统计笔记数（按 content_hash 去重）
        cur.execute("SELECT COUNT(DISTINCT content_hash) FROM learning_behavior")
        total_notes = cur.fetchone()[0]

        # 标签分布
        cur.execute("""
            SELECT tag, COUNT(*) as cnt
            FROM learning_behavior
            GROUP BY tag
            ORDER BY cnt DESC
            LIMIT 20
        """)
        tag_dist = [{"tag": r[0], "count": r[1]} for r in cur.fetchall()]

        # 来源分布
        cur.execute("""
            SELECT source, COUNT(DISTINCT content_hash) as cnt
            FROM learning_behavior
            GROUP BY source
            ORDER BY cnt DESC
        """)
        source_dist = [{"source": r[0], "count": r[1]} for r in cur.fetchall()]

        # 每日学习数（最近 N 天）
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        cur.execute("""
            SELECT learn_date, COUNT(DISTINCT content_hash) as cnt
            FROM learning_behavior
            WHERE learn_date >= ?
            GROUP BY learn_date
            ORDER BY learn_date
        """, (since_date,))
        daily = [{"date": r[0], "count": r[1]} for r in cur.fetchall()]

        # 连续学习天数（从今天往前数）
        cur.execute("""
            SELECT DISTINCT learn_date
            FROM learning_behavior
            ORDER BY learn_date DESC
        """)
        all_dates = [r[0] for r in cur.fetchall()]
        streak = self._calc_streak(all_dates)

        # 最近 5 条笔记
        cur.execute("""
            SELECT DISTINCT title, source, learn_date
            FROM learning_behavior
            ORDER BY learn_date DESC, id DESC
            LIMIT 5
        """)
        latest = [
            {"title": r[0], "source": r[1], "learn_date": r[2]}
            for r in cur.fetchall()
        ]

        conn.close()

        return {
            "total_notes": total_notes,
            "total_tags": len(tag_dist),
            "total_sources": len(source_dist),
            "tag_distribution": tag_dist,
            "source_distribution": source_dist,
            "daily_counts": daily,
            "streak": streak,
            "latest_notes": latest,
            "period_days": days,
        }

    def _calc_streak(self, dates: list[str]) -> int:
        """计算连续学习天数。从今天或昨天往前数。"""
        if not dates:
            return 0

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # 如果今天没学但昨天学了，也算（防止半夜断连）
        check_date = today if today in dates else (yesterday if yesterday in dates else None)
        if check_date is None:
            return 0

        date_set = set(dates)
        streak = 0
        d = datetime.strptime(check_date, "%Y-%m-%d")
        while d.strftime("%Y-%m-%d") in date_set:
            streak += 1
            d -= timedelta(days=1)
        return streak


# 单例
inbox_scanner = InboxScanner()
