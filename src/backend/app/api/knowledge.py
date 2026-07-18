"""Knowledge graph API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import auth_guard
from app.services import knowledge

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/search", dependencies=[Depends(auth_guard(("ceo", "manager", "assistant")))])
def search_knowledge(q: str = Query(..., min_length=1), limit: int = 20):
    """Full-text search across all business knowledge and schemas."""
    return {"results": knowledge.search(q, limit)}


@router.get("/topics", dependencies=[Depends(auth_guard(("ceo", "manager", "assistant")))])
def get_topics():
    """Knowledge map grouped by topic."""
    return {"topics": knowledge.topics()}


@router.get("/nodes/{node_id}", dependencies=[Depends(auth_guard(("ceo", "manager", "assistant")))])
def get_node(node_id: str):
    """Retrieve full content of a single knowledge node."""
    node = knowledge.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.post("/refresh", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def refresh_index():
    """Force a re-index of all documentation files."""
    return knowledge.refresh()
