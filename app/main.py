"""
AI Knowledge Hub - 主入口
启动 FastAPI 服务 + 定时任务调度
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from rich.console import Console

from app.api.routes import router
from app.config import settings
from app.core.llm import llm_service
from app.core.rag import rag

console = Console()

# 定时任务调度器
scheduler = AsyncIOScheduler()


async def daily_github_collect():
    """每日 GitHub 热点收集（08:00 执行）"""
    console.print("[bold blue]开始每日 GitHub 热点收集...[/bold blue]")
    from app.services.github_collector import github_collector
    from app.integrations.feishu_notifier import feishu_notifier

    try:
        result = await github_collector.collect_daily()
        console.print(f"[green]收集完成: {result['total']} 个项目[/green]")
        console.print(f"  日报路径: {result['markdown_path']}")

        # 推送飞书通知
        await feishu_notifier.notify_github_hot(result)
        console.print("[green]飞书通知已推送[/green]")
    except Exception as e:
        console.print(f"[red]收集失败: {e}[/red]")


async def daily_vault_sync():
    """每日 Vault 向量化同步（02:00 执行）"""
    console.print("[bold blue]开始每日 Vault 向量化同步...[/bold blue]")
    try:
        count = rag.index_vault()
        console.print(f"[green]同步完成: {count} 个文档块[/green]")
    except Exception as e:
        console.print(f"[red]同步失败: {e}[/red]")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    console.print("\n[bold cyan]========================================[/bold cyan]")
    console.print("[bold cyan]  AI Knowledge Hub 启动中...[/bold cyan]")
    console.print("[bold cyan]========================================[/bold cyan]\n")

    # 检查 Ollama
    ollama_ok = llm_service.check_ollama()
    if ollama_ok:
        console.print(f"[green]Ollama 已连接 | 模型: {settings.OLLAMA_MODEL}[/green]")
    else:
        console.print("[yellow]Ollama 未连接，将使用 DeepSeek API 作为备用[/yellow]")

    # 检查 Vault
    vault = settings.vault_path_obj
    if vault.exists():
        console.print(f"[green]Vault 路径: {vault}[/green]")
    else:
        console.print(f"[yellow]Vault 路径不存在: {vault}[/yellow]")
        console.print("[yellow]请运行: python scripts/init_vault.py[/yellow]")

    # 初始化 ChromaDB
    try:
        rag.notes_collection.count()
        console.print("[green]ChromaDB 已连接[/green]")
    except Exception as e:
        console.print(f"[red]ChromaDB 初始化失败: {e}[/red]")

    # 初始化 SQLite 数据库
    try:
        from scripts.init_db import init_database
        init_database()
    except Exception as e:
        console.print(f"[yellow]SQLite 初始化跳过: {e}[/yellow]")

    # 配置定时任务
    scheduler.add_job(
        daily_github_collect,
        CronTrigger(hour=8, minute=0),
        id="github_collect",
        replace_existing=True,
    )
    scheduler.add_job(
        daily_vault_sync,
        CronTrigger(hour=2, minute=0),
        id="vault_sync",
        replace_existing=True,
    )
    scheduler.start()
    console.print("[green]定时任务已启动 (GitHub收集: 08:00, Vault同步: 02:00)[/green]")

    console.print("\n[bold green]AI Knowledge Hub 已就绪[/bold green]")
    console.print(f"[bold green]API 文档: http://localhost:8000/docs[/bold green]\n")

    yield

    scheduler.shutdown()
    console.print("[yellow]AI Knowledge Hub 已关闭[/yellow]")


app = FastAPI(
    title="AI Knowledge Hub",
    description="个人 AI 知识中台 - Obsidian + Ollama + GitHub + WeChat",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS（允许 Obsidian 插件和微信桥接服务跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
