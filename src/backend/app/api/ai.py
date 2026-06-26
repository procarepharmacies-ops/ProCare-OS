"""AI assistant endpoint (read-only Arabic-first chat)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import ai

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatIn(BaseModel):
    query: str
    branch_id: int | None = None
    lang: str = "ar"


@router.post("/chat")
def chat(payload: ChatIn, session: Session = Depends(get_session)):
    return ai.chat(session, payload.query, payload.branch_id or None, payload.lang)


@router.get("/intents")
def intents():
    """The whitelist of read-only intents the assistant can serve."""
    return {"intents": ai.INTENTS}
