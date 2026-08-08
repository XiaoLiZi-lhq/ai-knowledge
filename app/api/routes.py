"""
AI Knowledge Hub - API 路由
所有 REST API 端点
"""

from fastapi import APIRouter, Header, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional
from app.config import settings
from app.core.rag import rag
from app.core.llm import llm_service
from app.services.github_collector import github_collector
from app.services.ai_tutor import quiz_generator, gap_scanner, plan_generator
from app.services.note_organizer import note_organizer
from app.integrations.wechat_bridge import wechat_router

router = APIRouter(prefix="/api/v1")


def verify_api_key(authorization: Optional[str] = Header(None)):
    """简单的 API Key 验证"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API key")
    token = authorization.split(" ", 1)[1]
    if token != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True


# ============ 请求/响应模型 ============

class ChatRequest(BaseModel):
    query: str
    history: Optional[list[dict]] = None

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]

class QuizRequest(BaseModel):
    topic: Optional[str] = ""
    count: int = 5
    type: str = "mixed"

class QuizSubmitRequest(BaseModel):
    answers: list[dict]

class PlanRequest(BaseModel):
    goal: str
    duration_days: int = 14

class OrganizeRequest(BaseModel):
    note_path: str

class SyncRequest(BaseModel):
    force: bool = False

class WeChatMessage(BaseModel):
    message: str
    sender: str = ""


# ============ 健康检查 ============

@router.get("/health")
async def health_check():
    """健康检查 - 无需认证"""
    ollama_ok = llm_service.check_ollama()
    chroma_ok = True
    try:
        rag.notes_collection.count()
    except Exception:
        chroma_ok = False

    return {
        "status": "ok" if ollama_ok and chroma_ok else "degraded",
        "ollama": "connected" if ollama_ok else "disconnected",
        "chromadb": "connected" if chroma_ok else "disconnected",
        "model": settings.OLLAMA_MODEL,
    }


# ============ RAG 问答 ============

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, auth: bool = Depends(verify_api_key)):
    """RAG 知识库问答"""
    result = rag.answer(req.query, req.history)
    return ChatResponse(answer=result["answer"], sources=result["sources"])


# ============ AI 导师 ============

@router.post("/quiz/generate")
async def quiz_generate(req: QuizRequest, auth: bool = Depends(verify_api_key)):
    """AI 出题"""
    return quiz_generator.generate(topic=req.topic, count=req.count, quiz_type=req.type)


@router.post("/quiz/submit")
async def quiz_submit(req: QuizSubmitRequest, auth: bool = Depends(verify_api_key)):
    """提交测验答案"""
    return quiz_generator.submit(req.answers)


@router.get("/gaps/scan")
async def gaps_scan(domain: str = "", auth: bool = Depends(verify_api_key)):
    """知识盲区扫描"""
    return gap_scanner.scan(domain=domain)


@router.post("/plan/generate")
async def plan_generate(req: PlanRequest, auth: bool = Depends(verify_api_key)):
    """生成学习计划"""
    return plan_generator.generate(goal=req.goal, duration_days=req.duration_days)


# ============ GitHub 热点 ============

@router.get("/hot/today")
async def hot_today(auth: bool = Depends(verify_api_key)):
    """获取今日 GitHub 热点"""
    return {"items": github_collector.get_today()}


@router.post("/hot/collect")
async def hot_collect(background_tasks: BackgroundTasks, auth: bool = Depends(verify_api_key)):
    """手动触发 GitHub 热点收集"""
    background_tasks.add_task(_run_collect)
    return {"status": "collecting", "message": "后台收集中，约1-3分钟完成"}


async def _run_collect():
    """后台执行收集"""
    import asyncio
    result = await github_collector.collect_daily()
    # 推送通知
    from app.integrations.feishu_notifier import feishu_notifier
    await feishu_notifier.notify_github_hot(result)
    return result


# ============ 笔记管理 ============

@router.post("/notes/sync")
async def notes_sync(req: SyncRequest, auth: bool = Depends(verify_api_key)):
    """触发 Vault 向量化同步"""
    count = rag.index_vault(force=req.force)
    return {"synced_chunks": count}


@router.post("/notes/organize")
async def notes_organize(req: OrganizeRequest, auth: bool = Depends(verify_api_key)):
    """AI 整理笔记"""
    return note_organizer.organize(req.note_path)


# ============ 微信接口 ============

@router.post("/wechat/message")
async def wechat_message(msg: WeChatMessage, auth: bool = Depends(verify_api_key)):
    """接收微信消息并返回回复（供微信桥接服务调用）"""
    reply = wechat_router.handle_message(msg.message, msg.sender)
    return {"reply": reply}
