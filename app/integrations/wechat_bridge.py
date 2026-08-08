"""
AI Knowledge Hub - 微信桥接
通过 HTTP Webhook 接收微信消息，路由到对应处理器

注意：wcferry 仅支持 Windows。Mac/Linux 环境建议：
1. 企业微信 Webhook（最安全）
2. 微信测试号 + 自建服务
3. 第三方桥接（如 WeChat Bot CLI）

本模块提供统一的指令路由，可对接任意微信接入方案。
"""

from typing import Callable, Optional
from app.core.rag import rag
from app.services.ai_tutor import quiz_generator, gap_scanner, plan_generator
from app.services.github_collector import github_collector
from app.services.note_organizer import note_organizer
from app.config import settings
from pathlib import Path
from datetime import datetime


class WeChatRouter:
    """微信消息指令路由"""

    def __init__(self):
        self.commands = {
            "/hot": self._cmd_hot,
            "/quiz": self._cmd_quiz,
            "/plan": self._cmd_plan,
            "/scan": self._cmd_scan,
            "/search": self._cmd_search,
            "/add": self._cmd_add,
            "/help": self._cmd_help,
        }

    def handle_message(self, message: str, sender: str = "") -> str:
        """
        处理微信消息，返回回复内容
        支持指令和自然语言问答
        """
        if not sender or (settings.WECHAT_WHITE_LIST and sender not in settings.WECHAT_WHITE_LIST):
            return "抱歉，您没有权限使用此助手。"

        message = message.strip()

        # 指令路由
        for cmd, handler in self.commands.items():
            if message.lower().startswith(cmd):
                args = message[len(cmd):].strip()
                return handler(args)

        # 默认：RAG 知识库问答
        return self._rag_chat(message)

    def _rag_chat(self, query: str) -> str:
        """RAG 知识库问答"""
        result = rag.answer(query)
        reply = result["answer"]
        if result["sources"]:
            reply += "\n\n来源：\n"
            for s in result["sources"][:3]:
                reply += f"- {s['title']}\n"
        return reply

    def _cmd_hot(self, args: str) -> str:
        """/hot - 查看今日 GitHub 热点"""
        items = github_collector.get_today()
        if not items:
            return "今日热点尚未收集，请稍后再试或手动触发收集。"

        lang_filter = args.lower() if args else ""
        filtered = [i for i in items if not lang_filter or lang_filter in i.get("language", "").lower()]

        lines = [f"GitHub 热点 | {datetime.now().strftime('%m月%d日')}\n"]
        for i, item in enumerate(filtered[:10], 1):
            summary = item.get("summary", item.get("description", ""))[:80]
            lines.append(f"{i}. {item['repo_name']}")
            lines.append(f"   Star: {item.get('stars', 0)} | {item.get('language', '')}")
            lines.append(f"   {summary}\n")

        return "\n".join(lines)

    def _cmd_quiz(self, args: str) -> str:
        """/quiz [主题] - AI 出题"""
        topic = args.strip()
        result = quiz_generator.generate(topic=topic, count=3, quiz_type="choice")

        if "error" in result:
            return result["error"]

        lines = [f"测验开始 | 主题: {topic or '综合'}\n"]
        for i, q in enumerate(result.get("questions", []), 1):
            lines.append(f"Q{i}: {q['question']}")
            if q.get("options"):
                for j, opt in enumerate(q["options"]):
                    lines.append(f"  {chr(65+j)}. {opt}")
            lines.append("")

        lines.append("回复答案格式：Q1:B Q2:A Q3:C")
        return "\n".join(lines)

    def _cmd_plan(self, args: str) -> str:
        """/plan [目标] [天数] - 生成学习计划"""
        parts = args.split()
        goal = parts[0] if parts else "AI综合提升"
        days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 14

        result = plan_generator.generate(goal=goal, duration_days=days)

        if "error" in result:
            return result["error"]

        lines = [f"学习计划: {result.get('title', goal)}\n"]
        lines.append(f"目标: {result.get('goal', goal)}")
        lines.append(f"周期: {result.get('start_date', '')} ~ {result.get('end_date', '')}\n")

        for week in result.get("weeks", []):
            lines.append(f"Week {week.get('week', '')}: {week.get('theme', '')}")
            for day in week.get("days", []):
                lines.append(f"  {day.get('date', '')} - {day.get('task', '')}")
            lines.append(f"  检验: {week.get('checkpoint', '')}\n")

        lines.append("完整计划已写入 Obsidian Vault")
        return "\n".join(lines)

    def _cmd_scan(self, args: str) -> str:
        """/scan [领域] - 知识盲区扫描"""
        domain = args.strip()
        result = gap_scanner.scan(domain=domain)

        lines = ["知识盲区扫描报告\n"]
        lines.append("覆盖概览:")
        for domain_name, percent in result.get("coverage", {}).items():
            lines.append(f"  {domain_name}: {percent}%")
        lines.append("")

        if result.get("total_gaps", 0) > 0:
            lines.append(f"发现 {result['total_gaps']} 个盲区:\n")
            for detail in result.get("details", []):
                for gap in detail.get("gaps", [])[:3]:
                    lines.append(f"  [{detail['domain']}] {gap['topic']} - {gap['suggestion']}")
        else:
            lines.append("知识覆盖良好，暂无明显盲区。")

        return "\n".join(lines)

    def _cmd_search(self, args: str) -> str:
        """/search [关键词] - 搜索笔记"""
        if not args:
            return "用法: /search 注意力机制"

        results = rag.retrieve(args, top_k=5)
        if not results:
            return f"未找到与「{args}」相关的笔记。"

        lines = [f"搜索「{args}」结果:\n"]
        for i, r in enumerate(results, 1):
            title = r["metadata"].get("title", "未知")
            lines.append(f"{i}. {title}")
            preview = r["content"][:100].replace("\n", " ")
            lines.append(f"   {preview}...\n")

        return "\n".join(lines)

    def _cmd_add(self, args: str) -> str:
        """/add [内容] - 快速记录到 Inbox"""
        if not args:
            return "用法: /add 突然想到的灵感"

        vault = settings.vault_path_obj
        inbox = vault / "00-Inbox"
        inbox.mkdir(parents=True, exist_ok=True)

        filename = f"quick-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        filepath = inbox / filename

        content = f"""---
created: {datetime.now().isoformat()}
source: wechat
tags: [inbox, quick-note]
---

# 快速记录

{args}
"""
        filepath.write_text(content, encoding="utf-8")
        return f"已记录到 Inbox: {filename}"

    def _cmd_help(self, args: str) -> str:
        """/help - 查看所有指令"""
        return """AI 知识助手指令：

直接发消息 = 知识库问答
/hot [语言] - 今日GitHub热点
/quiz [主题] - AI出题测验
/plan [目标] [天数] - 生成学习计划
/scan [领域] - 知识盲区扫描
/search [关键词] - 搜索笔记
/add [内容] - 快速记录到Inbox
/help - 查看本帮助"""


wechat_router = WeChatRouter()
