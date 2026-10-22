#!/usr/bin/env python3
"""
AI Knowledge Hub - 桌面投递箱同步脚本

用法:
    python scripts/sync_inbox.py           # 扫描导入
    python scripts/sync_inbox.py --preview # 仅预览
    python scripts/sync_inbox.py --force   # 强制重新导入（忽略去重）

可加入 crontab 定时执行:
    0 */4 * * * cd /path/to/ai-knowledge-hub && python scripts/sync_inbox.py >> logs/inbox_sync.log 2>&1
"""

import sys
import os
import json

# 把项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.inbox_scanner import inbox_scanner


def main():
    args = sys.argv[1:]

    if "--preview" in args:
        print("=== 投递箱预览 ===")
        result = inbox_scanner.preview()
        print(f"总文件: {result['total_files']} | 待导入: {result['pending']} | 已同步: {result['already_synced']}")
        print()
        for f in result["files"]:
            status = "已导入" if f["already_synced"] else "待导入"
            print(f"  [{status}] {f['title']}")
            print(f"          来源: {f['source']} | 标签: {f['tags']} | {f['size']}B")
            print(f"          预览: {f['preview'][:80]}...")
        return

    if "--stats" in args:
        print("=== 学习行为统计 ===")
        stats = inbox_scanner.learning_stats()
        print(f"总笔记: {stats['total_notes']} | 连续学习: {stats['streak']} 天")
        print(f"主题数: {stats['total_tags']} | 来源数: {stats['total_sources']}")
        print("\n主题分布:")
        for t in stats["tag_distribution"]:
            print(f"  {t['tag']}: {t['count']}")
        print("\n来源分布:")
        for s in stats["source_distribution"]:
            print(f"  {s['source']}: {s['count']}")
        return

    force = "--force" in args
    print(f"=== 开始同步{'（强制模式）' if force else ''} ===")
    result = inbox_scanner.sync(force=force)

    print(f"扫描: {result['scanned']} | 导入: {result['imported']} | 跳过: {result['skipped']} | 错误: {result['errors']}")
    print(f"用时: {result['duration_seconds']}s")

    if result["errors"] > 0:
        print("\n错误详情:")
        for d in result["details"]:
            if d["status"] == "error":
                print(f"  {d['file']}: {d.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
