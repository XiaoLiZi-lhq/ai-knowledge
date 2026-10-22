"""
AI Knowledge Hub - WorkBuddy 跨空间学习记录同步服务

扫描所有 WorkBuddy 空间的 .workbuddy/memory/*.md 文件，
智能分类后导入到 Obsidian Vault 和 SQLite，实现学习记录的统一管理。
"""

import hashlib
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import settings


class WorkBuddySync:
    """WorkBuddy 跨空间同步引擎"""

    # WorkBuddy 根目录（所有空间的父目录）
    WORKBUDDY_ROOT = Path.home() / "WorkBuddy"

    # Vault 目标子文件夹
    VAULT_DAILY_DIR = "04-Daily"
    VAULT_LEARNING_DIR = "05-Learning"
    VAULT_RESOURCES_DIR = "02-Resources"

    def __init__(self):
        self.vault = settings.vault_path_obj
        self.db_path = settings.SQLITE_PATH
        self._ensure_vault_dirs()

    def _ensure_vault_dirs(self):
        """确保 Vault 目标目录存在"""
        for d in [self.VAULT_DAILY_DIR, self.VAULT_LEARNING_DIR, self.VAULT_RESOURCES_DIR]:
            (self.vault / d).mkdir(parents=True, exist_ok=True)

    # ============ 扫描 ============

    def scan_all_spaces(self) -> list[dict]:
        """
        扫描所有 WorkBuddy 空间，返回发现的记忆文件列表。
        每个条目: {workspace, file_path, file_type, mtime, size, content_hash, content_preview}
        """
        results = []
        if not self.WORKBUDDY_ROOT.exists():
            return results

        for space_dir in sorted(self.WORKBUDDY_ROOT.iterdir()):
            if not space_dir.is_dir():
                continue
            mem_dir = space_dir / ".workbuddy" / "memory"
            if not mem_dir.exists():
                continue

            for md_file in sorted(mem_dir.glob("*.md")):
                info = self._analyze_file(space_dir.name, md_file)
                if info:
                    results.append(info)

        return results

    def _analyze_file(self, workspace: str, md_file: Path) -> Optional[dict]:
        """分析单个记忆文件"""
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            return None

        if not content.strip():
            return None

        # 文件类型判定
        file_type = self._classify_file(md_file.name, content)

        # 内容哈希用于去重
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

        # 预览
        preview = content[:200].replace("\n", " ").strip()

        return {
            "workspace": workspace,
            "file_path": str(md_file),
            "file_name": md_file.name,
            "file_type": file_type,
            "mtime": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat(),
            "size": md_file.stat().st_size,
            "content_hash": content_hash,
            "content_preview": preview,
            "content": content,
        }

    def _classify_file(self, filename: str, content: str) -> str:
        """
        分类文件类型:
        - daily: YYYY-MM-DD.md 格式的日志
        - long_term: MEMORY.md 长期记忆
        - artifact: 其他 .md 成果产物
        """
        if filename == "MEMORY.md":
            return "long_term"

        # YYYY-MM-DD.md 格式
        if re.match(r"\d{4}-\d{2}-\d{2}\.md$", filename):
            return "daily"

        return "artifact"

    # ============ 同步 ============

    def sync(self, force: bool = False) -> dict:
        """
        执行全量同步。返回统计报告。

        Args:
            force: True 时忽略去重，强制重新导入
        """
        start = datetime.now()
        files = self.scan_all_spaces()

        stats = {
            "scanned": len(files),
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "categories": {"daily": 0, "long_term": 0, "artifact": 0},
            "details": [],
        }

        already_synced = set() if force else self._load_synced_hashes()

        for f in files:
            try:
                if f["content_hash"] in already_synced:
                    stats["skipped"] += 1
                    stats["details"].append({
                        "file": f["file_name"],
                        "workspace": f["workspace"],
                        "status": "skipped",
                    })
                    continue

                target_path = self._import_to_vault(f)
                self._log_to_sqlite(f, target_path)

                already_synced.add(f["content_hash"])
                stats["imported"] += 1
                stats["categories"][f["file_type"]] += 1
                stats["details"].append({
                    "file": f["file_name"],
                    "workspace": f["workspace"],
                    "status": "imported",
                    "target": str(target_path),
                    "type": f["file_type"],
                })
            except Exception as e:
                stats["errors"] += 1
                stats["details"].append({
                    "file": f["file_name"],
                    "workspace": f["workspace"],
                    "status": "error",
                    "error": str(e),
                })

        stats["duration_seconds"] = round((datetime.now() - start).total_seconds(), 2)
        stats["synced_at"] = datetime.now().isoformat()
        return stats

    def _import_to_vault(self, file_info: dict) -> Path:
        """将文件导入到 Vault 对应目录，返回目标路径"""
        file_type = file_info["file_type"]
        workspace = file_info["workspace"]
        filename = file_info["file_name"]
        content = file_info["content"]

        # 根据类型选择目标目录
        if file_type == "daily":
            target_dir = self.vault / self.VAULT_DAILY_DIR
            # 日志文件保留原文件名，加上空间标识
            target_name = f"WB-{workspace}-{filename}"
        elif file_type == "long_term":
            target_dir = self.vault / self.VAULT_LEARNING_DIR
            target_name = f"WB-{workspace}-MEMORY.md"
        else:
            target_dir = self.vault / self.VAULT_RESOURCES_DIR
            stem = Path(filename).stem
            target_name = f"WB-{workspace}-{stem}.md"

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / target_name

        # 写入带 frontmatter 的内容
        frontmatter_text = self._build_frontmatter(file_info)
        full_content = f"---\n{frontmatter_text}---\n\n{content}\n"
        target_path.write_text(full_content, encoding="utf-8")

        return target_path

    def _build_frontmatter(self, file_info: dict) -> str:
        """构建 Obsidian frontmatter"""
        return (
            f"source: workbuddy\n"
            f"workspace: {file_info['workspace']}\n"
            f"source_file: {file_info['file_name']}\n"
            f"imported_at: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"source_mtime: {file_info['mtime'][:10]}\n"
            f"content_hash: {file_info['content_hash']}\n"
            f"tags:\n"
            f"  - workbuddy-sync\n"
            f"  - {file_info['file_type']}\n"
        )

    def _log_to_sqlite(self, file_info: dict, target_path: Path):
        """将同步记录写入 SQLite learning_log 表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 确保表存在
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workbuddy_sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE NOT NULL,
                workspace TEXT NOT NULL,
                source_file TEXT NOT NULL,
                file_type TEXT NOT NULL,
                vault_path TEXT NOT NULL,
                synced_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        cursor.execute(
            """INSERT OR REPLACE INTO workbuddy_sync_log
               (content_hash, workspace, source_file, file_type, vault_path)
               VALUES (?, ?, ?, ?, ?)""",
            (
                file_info["content_hash"],
                file_info["workspace"],
                file_info["file_name"],
                file_info["file_type"],
                str(target_path),
            ),
        )

        # 同时写入 learning_log
        cursor.execute(
            """INSERT INTO learning_log (date, activity, topic, score)
               VALUES (?, ?, ?, ?)""",
            (
                file_info["mtime"][:10],
                f"WorkBuddy 同步导入",
                f"{file_info['workspace']}/{file_info['file_name']}",
                None,
            ),
        )

        conn.commit()
        conn.close()

    def _load_synced_hashes(self) -> set[str]:
        """从数据库加载已同步的 content_hash 集合"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workbuddy_sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE NOT NULL,
                workspace TEXT NOT NULL,
                source_file TEXT NOT NULL,
                file_type TEXT NOT NULL,
                vault_path TEXT NOT NULL,
                synced_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        cursor.execute("SELECT content_hash FROM workbuddy_sync_log")
        hashes = {row[0] for row in cursor.fetchall()}
        conn.close()
        return hashes

    # ============ 预览模式 ============

    def preview(self) -> dict:
        """预览扫描结果但不实际导入"""
        files = self.scan_all_spaces()
        already_synced = self._load_synced_hashes()

        return {
            "total_files": len(files),
            "already_synced": sum(1 for f in files if f["content_hash"] in already_synced),
            "pending": sum(1 for f in files if f["content_hash"] not in already_synced),
            "workspaces": sorted(set(f["workspace"] for f in files)),
            "files": [
                {
                    "workspace": f["workspace"],
                    "file_name": f["file_name"],
                    "file_type": f["file_type"],
                    "size": f["size"],
                    "preview": f["content_preview"],
                    "already_synced": f["content_hash"] in already_synced,
                }
                for f in files
            ],
        }


# 单例
workbuddy_sync = WorkBuddySync()
