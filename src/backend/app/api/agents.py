"""Agent orchestration API routes."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db.base import get_session
from app.services import agent_orchestration

router = APIRouter(prefix="/agents", tags=["agents"])


class DispatchRequest(BaseModel):
    task: str
    workspace: str | None = None
    task_id: int | None = None
    confirm: bool = False
    dry_run: bool | None = None


@router.get("/status", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def get_status():
    """Return the online/dispatchable status of the agent fleet."""
    return agent_orchestration.agent_status()


@router.post("/{agent_id}/dispatch", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def dispatch_task(
    agent_id: str,
    req: DispatchRequest,
    session: Session = Depends(get_session),
):
    """Dispatch a task to a specific AI agent."""
    result = agent_orchestration.dispatch(
        agent=agent_id,
        task=req.task,
        session=session,
        workspace=req.workspace,
        task_id=req.task_id,
        confirm=req.confirm,
        dry_run=req.dry_run,
    )
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result)
    return result


@router.get("/runs", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def get_runs(limit: int = 50, session: Session = Depends(get_session)):
    """Return the recent execution history of all agents."""
    return {"runs": agent_orchestration.recent_runs(session, limit)}
