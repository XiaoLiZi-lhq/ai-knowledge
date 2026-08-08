"""
AI Knowledge Hub - 飞书通知服务
通过 Webhook 推送消息到飞书群
"""

import httpx
from app.config import settings


class FeishuNotifier:
    """飞书 Webhook 通知"""

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or ""  # 从配置加载

    async def send_text(self, text: str) -> bool:
        """发送文本消息"""
        if not self.webhook_url:
            return False

        payload = {
            "msg_type": "text",
            "content": {"text": text},
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.webhook_url, json=payload, timeout=10)
                return resp.status_code == 200
        except Exception:
            return False

    async def send_card(self, title: str, content: str, url: str = "") -> bool:
        """发送卡片消息"""
        if not self.webhook_url:
            return False

        elements = [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**{title}**"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": content}},
        ]
        if url:
            elements.append({
                "tag": "action",
                "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看详情"},
                    "url": url,
                    "type": "primary",
                }],
            })

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title}},
                "elements": elements,
            },
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.webhook_url, json=payload, timeout=10)
                return resp.status_code == 200
        except Exception:
            return False

    async def notify_github_hot(self, hot_data: dict) -> bool:
        """推送 GitHub 热点通知"""
        title = f"GitHub 热点 | {hot_data.get('date', '')}"
        lines = [f"今日发现 {hot_data.get('total', 0)} 个值得关注的项目:\n"]
        for p in hot_data.get("top_projects", [])[:5]:
            lines.append(f"- {p['name']} ({p['stars']} Star)")
            lines.append(f"  {p['summary'][:60]}...\n")

        return await self.send_card(title, "\n".join(lines))


feishu_notifier = FeishuNotifier()
