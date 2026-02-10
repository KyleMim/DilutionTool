"""Notes API router for saving conversation notes and generating memos."""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from backend.database import SessionLocal, is_sqlite
from backend.models import Note, Conversation, Message
from backend.config import get_config
from backend.services.llm_client import LLMClient, build_company_context

router = APIRouter(prefix="/api/notes", tags=["notes"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Request/Response schemas ─────────────────────────────────────────

class NoteCreate(BaseModel):
    title: str
    content: str
    note_type: str = "note"  # "note" | "memo"
    ticker: Optional[str] = None


class NoteUpdate(BaseModel):
    title: str
    content: str


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str
    note_type: str
    ticker: Optional[str]
    conversation_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SaveFromConversationRequest(BaseModel):
    title: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("", response_model=NoteResponse)
def create_note(body: NoteCreate, db: Session = Depends(get_db)):
    note = Note(
        title=body.title,
        content=body.content,
        note_type=body.note_type,
        ticker=body.ticker.upper() if body.ticker else None,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    _fts_upsert(db, note)
    db.commit()
    return _to_response(note)


@router.get("", response_model=List[NoteResponse])
def list_notes(
    ticker: Optional[str] = Query(None),
    note_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Note)
    if ticker:
        query = query.filter(Note.ticker == ticker.upper())
    if note_type:
        query = query.filter(Note.note_type == note_type)
    notes = query.order_by(desc(Note.updated_at)).all()
    return [_to_response(n) for n in notes]


@router.get("/{note_id}", response_model=NoteResponse)
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).get(note_id)
    if not note:
        raise HTTPException(404, "Note not found")
    return _to_response(note)


@router.put("/{note_id}", response_model=NoteResponse)
def update_note(note_id: int, body: NoteUpdate, db: Session = Depends(get_db)):
    note = db.query(Note).get(note_id)
    if not note:
        raise HTTPException(404, "Note not found")
    note.title = body.title
    note.content = body.content
    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    _fts_upsert(db, note)
    db.commit()
    return _to_response(note)


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).get(note_id)
    if not note:
        raise HTTPException(404, "Note not found")
    _fts_delete(db, note.id)
    db.delete(note)
    db.commit()


@router.post("/from-conversation/{conversation_id}", response_model=NoteResponse)
def save_conversation_as_note(
    conversation_id: int,
    body: SaveFromConversationRequest,
    db: Session = Depends(get_db),
):
    """Save a conversation as a raw note."""
    conv = db.query(Conversation).get(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    messages = (
        db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at)
        .all()
    )

    # Format conversation as markdown
    content_parts = []
    for msg in messages:
        role_label = "You" if msg.role == "user" else "AI Assistant"
        content_parts.append(f"### {role_label}\n{msg.content}")

    content = "\n\n---\n\n".join(content_parts)
    title = body.title or conv.title or f"Notes from chat"
    if conv.ticker:
        title = f"{conv.ticker} - {title}"

    note = Note(
        title=title,
        content=content,
        note_type="note",
        ticker=conv.ticker,
        conversation_id=conversation_id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    _fts_upsert(db, note)
    db.commit()
    return _to_response(note)


@router.post("/memo-from-conversation/{conversation_id}", response_model=NoteResponse)
def generate_memo_from_conversation(
    conversation_id: int,
    body: SaveFromConversationRequest,
    db: Session = Depends(get_db),
):
    """Generate a structured memo from a conversation using AI."""
    conv = db.query(Conversation).get(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    cfg = get_config()
    if not cfg.anthropic_api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")

    messages = (
        db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at)
        .all()
    )

    # Build conversation text
    conversation_text = ""
    for msg in messages:
        role_label = "User" if msg.role == "user" else "Assistant"
        conversation_text += f"\n{role_label}: {msg.content}\n"

    # Build company context if applicable
    company_context = ""
    if conv.ticker:
        company_context = build_company_context(db, conv.ticker)

    # Generate memo via LLM
    llm = LLMClient(api_key=cfg.anthropic_api_key, model=cfg.llm_model)
    memo_content = llm.generate_memo(conversation_text, company_context)

    title = body.title or f"Investment Memo"
    if conv.ticker:
        title = f"{conv.ticker} - {title}"

    note = Note(
        title=title,
        content=memo_content,
        note_type="memo",
        ticker=conv.ticker,
        conversation_id=conversation_id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    _fts_upsert(db, note)
    db.commit()
    return _to_response(note)


def _fts_upsert(db: Session, note: Note):
    """Insert or update the FTS index for a note (SQLite only)."""
    if not is_sqlite():
        return
    db.execute(text("DELETE FROM notes_fts WHERE rowid = :id"), {"id": note.id})
    db.execute(
        text(
            "INSERT INTO notes_fts(rowid, title, content, ticker, note_type) "
            "VALUES (:id, :title, :content, :ticker, :note_type)"
        ),
        {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "ticker": note.ticker or "",
            "note_type": note.note_type,
        },
    )


def _fts_delete(db: Session, note_id: int):
    """Remove a note from the FTS index (SQLite only)."""
    if not is_sqlite():
        return
    db.execute(text("DELETE FROM notes_fts WHERE rowid = :id"), {"id": note_id})


def _to_response(note: Note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        title=note.title,
        content=note.content,
        note_type=note.note_type,
        ticker=note.ticker,
        conversation_id=note.conversation_id,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )
