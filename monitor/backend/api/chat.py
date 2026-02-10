"""Chat API router for AI agent conversations."""

import json
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Conversation, Message
from backend.config import get_config
from backend.services.llm_client import LLMClient, build_company_context, SYSTEM_PROMPT_GLOBAL

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_llm_client() -> LLMClient:
    cfg = get_config()
    if not cfg.anthropic_api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")
    return LLMClient(api_key=cfg.anthropic_api_key, model=cfg.llm_model)


# ── Request/Response schemas ─────────────────────────────────────────

class ConversationCreate(BaseModel):
    ticker: Optional[str] = None
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: str


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: int
    title: Optional[str]
    ticker: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    id: int
    title: Optional[str]
    ticker: Optional[str]
    created_at: datetime
    messages: List[MessageResponse]

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(body: ConversationCreate, db: Session = Depends(get_db)):
    conv = Conversation(
        ticker=body.ticker.upper() if body.ticker else None,
        title=body.title,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        ticker=conv.ticker,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
    )


@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(
    ticker: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Conversation)
    if ticker:
        query = query.filter(Conversation.ticker == ticker.upper())
    conversations = query.order_by(desc(Conversation.updated_at)).all()
    return [
        ConversationResponse(
            id=c.id,
            title=c.title,
            ticker=c.ticker,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=len(c.messages),
        )
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).get(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        ticker=conv.ticker,
        created_at=conv.created_at,
        messages=[
            MessageResponse(
                id=m.id, role=m.role, content=m.content, created_at=m.created_at
            )
            for m in conv.messages
        ],
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).get(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    db.delete(conv)
    db.commit()


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
def rename_conversation(
    conversation_id: int,
    body: ConversationUpdate,
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).get(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    conv.title = body.title
    db.commit()
    db.refresh(conv)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        ticker=conv.ticker,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(conv.messages),
    )


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: int,
    body: MessageCreate,
):
    """Send a user message and stream back the AI response via SSE.

    The agent has access to tools:
    - lookup_company_profile: Fresh company data from FMP
    - lookup_fundamentals: Quarterly financials from FMP
    - lookup_stock_price: Historical prices from FMP
    - lookup_dilution_score: Internal dilution scores + SEC filings
    - search_notes: Previous research notes and memos
    """
    # Use a dedicated session for the streaming lifecycle
    db = SessionLocal()
    cfg = get_config()
    try:
        conv = db.query(Conversation).get(conversation_id)
        if not conv:
            db.close()
            raise HTTPException(404, "Conversation not found")

        if not cfg.anthropic_api_key:
            db.close()
            raise HTTPException(503, "ANTHROPIC_API_KEY not configured")

        # Save user message
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=body.content,
        )
        db.add(user_msg)
        db.commit()

        # Auto-title on first user message
        msg_count = db.query(Message).filter_by(
            conversation_id=conversation_id, role="user"
        ).count()
        if msg_count == 1 and not conv.title:
            conv.title = body.content[:80]
            db.commit()

        # Build message history
        all_messages = (
            db.query(Message)
            .filter_by(conversation_id=conversation_id)
            .order_by(Message.created_at)
            .all()
        )
        # Limit to last 30 messages to stay within context
        recent_messages = all_messages[-30:]
        llm_messages = [{"role": m.role, "content": m.content} for m in recent_messages]

        # Build system prompt
        if conv.ticker:
            system_prompt = build_company_context(db, conv.ticker)
        else:
            system_prompt = SYSTEM_PROMPT_GLOBAL

        llm = LLMClient(api_key=cfg.anthropic_api_key, model=cfg.llm_model)

    except HTTPException:
        raise
    except Exception as e:
        db.close()
        raise HTTPException(500, str(e))

    def event_generator():
        try:
            final_content = ""
            for event in llm.stream_with_tools(
                llm_messages, system_prompt, db, cfg.fmp_api_key
            ):
                if event["type"] == "tool_use":
                    # Notify frontend that a tool is being called
                    tool_name = event["tool"]
                    tool_input = event.get("input", {})
                    friendly = _tool_friendly_name(tool_name, tool_input)
                    yield f"data: {json.dumps({'type': 'tool_use', 'tool': tool_name, 'description': friendly})}\n\n"

                elif event["type"] == "chunk":
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']})}\n\n"

                elif event["type"] == "done":
                    final_content = event["content"]

            # Save assistant message
            if final_content:
                assistant_msg = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=final_content,
                )
                db.add(assistant_msg)
                conv.updated_at = datetime.utcnow()
                db.commit()
                yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _tool_friendly_name(tool_name: str, tool_input: dict) -> str:
    """Generate a user-friendly description of what tool is being used."""
    ticker = tool_input.get("ticker", "")
    query = tool_input.get("query", "")
    note_id = tool_input.get("note_id", "")
    descriptions = {
        "lookup_company_profile": f"Looking up {ticker} company profile...",
        "lookup_fundamentals": f"Fetching {ticker} quarterly financials...",
        "lookup_stock_price": f"Getting {ticker} stock price history...",
        "lookup_dilution_score": f"Checking {ticker} dilution score...",
        "search_notes": f"Searching notes{' for ' + query if query else ''}{' (' + ticker + ')' if ticker else ''}...",
        "get_note_detail": f"Reading note #{note_id}...",
        "web_search": f"Searching the web{' for ' + query if query else ''}...",
        "save_note": f"Saving {tool_input.get('note_type', 'note')}...",
        "update_note": f"Updating note #{tool_input.get('note_id', '')}...",
    }
    return descriptions.get(tool_name, f"Using {tool_name}...")
