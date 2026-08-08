"""
AI Knowledge Hub - 数据库初始化
创建 SQLite 学习记录表
"""

import sqlite3
import os
from app.config import settings


def init_database():
    """创建所有数据库表"""
    db_path = settings.SQLITE_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 学习日志表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            activity TEXT NOT NULL,
            topic TEXT,
            score INTEGER
        )
    """)

    # 学习计划表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            goal TEXT,
            tasks TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # 知识点掌握度表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_mastery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            mastery_level INTEGER DEFAULT 0,
            last_reviewed TEXT,
            review_count INTEGER DEFAULT 0
        )
    """)

    # GitHub 收集日志
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS github_collect_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            total INTEGER,
            markdown_path TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"数据库初始化完成: {db_path}")


if __name__ == "__main__":
    init_database()
