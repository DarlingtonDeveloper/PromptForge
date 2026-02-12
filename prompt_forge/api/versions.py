"""Version control endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from prompt_forge.api.models import (
    DiffResponse,
    RollbackRequest,
    VersionCreate,
    VersionResponse,
)
from prompt_forge.core.differ import StructuralDiffer
from prompt_forge.core.registry import PromptRegistry, get_registry
from prompt_forge.core.vcs import VersionControl, get_vcs
from prompt_forge.db.client import SupabaseClient, get_supabase_client

logger = structlog.get_logger()

router = APIRouter()


async def _auto_subscribe(
    prompt_id: str,
    agent_id: str | None,
    db: SupabaseClient,
) -> None:
    """Upsert subscription and update last_pulled_at."""
    if not agent_id:
        return
    existing = [
        r for r in db.select("prompt_subscriptions", filters={"prompt_id": prompt_id})
        if r["agent_id"] == agent_id
    ]
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        db.update("prompt_subscriptions", existing[0]["id"], {"last_pulled_at": now})
    else:
        db.insert("prompt_subscriptions", {
            "prompt_id": prompt_id,
            "agent_id": agent_id,
            "subscribed_at": now,
            "last_pulled_at": now,
        })


async def _notify_subscribers(
    prompt_id: str,
    slug: str,
    old_version: int,
    new_version: int,
    change_note: str,
    priority: str,
    db: SupabaseClient,
) -> None:
    """Publish targeted events to all subscribers."""
    try:
        from prompt_forge.core.events import get_event_publisher
        publisher = get_event_publisher()
        if not publisher._connected:
            return

        subs = db.select("prompt_subscriptions", filters={"prompt_id": prompt_id})
        for sub in subs:
            agent_id = sub["agent_id"]
            subject = f"swarm.forge.agent.{agent_id}.prompt-updated"
            await publisher.publish(
                event_type="prompt.updated",
                subject=subject,
                data={
                    "slug": slug,
                    "prompt_id": prompt_id,
                    "old_version": old_version,
                    "new_version": new_version,
                    "change_note": change_note,
                    "priority": priority,
                },
            )
            logger.info("subscription.notified", agent_id=agent_id, slug=slug, new_version=new_version)
    except Exception as e:
        logger.warning("subscription.notify_failed", error=str(e))


@router.post("/{slug}/versions", response_model=VersionResponse, status_code=201)
async def create_version(
    slug: str,
    data: VersionCreate,
    registry: PromptRegistry = Depends(get_registry),
    vcs: VersionControl = Depends(get_vcs),
    db: SupabaseClient = Depends(get_supabase_client),
) -> VersionResponse:
    """Commit a new version of a prompt."""
    prompt = registry.get_prompt(slug)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{slug}' not found")

    # Get old version number
    history = vcs.history(prompt_id=str(prompt["id"]), branch=data.branch, limit=1)
    old_version = history[0]["version"] if history else 0

    version = vcs.commit(
        prompt_id=str(prompt["id"]),
        content=data.content,
        message=data.message,
        author=data.author,
        branch=data.branch,
    )

    # Notify subscribers
    priority = getattr(data, 'priority', 'normal') or 'normal'
    await _notify_subscribers(
        prompt_id=str(prompt["id"]),
        slug=slug,
        old_version=old_version,
        new_version=version["version"],
        change_note=data.message,
        priority=priority,
        db=db,
    )

    return VersionResponse(**version)


@router.get("/{slug}/versions", response_model=list[VersionResponse])
async def list_versions(
    slug: str,
    branch: str = "main",
    limit: int = Query(default=50, le=200),
    registry: PromptRegistry = Depends(get_registry),
    vcs: VersionControl = Depends(get_vcs),
) -> list[VersionResponse]:
    """Get version history for a prompt."""
    prompt = registry.get_prompt(slug)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{slug}' not found")

    versions = vcs.history(prompt_id=str(prompt["id"]), branch=branch, limit=limit)
    return [VersionResponse(**v) for v in versions]


@router.get("/{slug}/versions/{version}", response_model=VersionResponse)
async def get_version(
    slug: str,
    version: int,
    branch: str = "main",
    x_agent_id: str | None = Header(default=None, alias="X-Agent-ID"),
    registry: PromptRegistry = Depends(get_registry),
    vcs: VersionControl = Depends(get_vcs),
    db: SupabaseClient = Depends(get_supabase_client),
) -> VersionResponse:
    """Get a specific version."""
    prompt = registry.get_prompt(slug)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{slug}' not found")

    ver = vcs.get_version(prompt_id=str(prompt["id"]), version=version, branch=branch)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    # Auto-subscribe
    await _auto_subscribe(str(prompt["id"]), x_agent_id, db)

    return VersionResponse(**ver)


@router.get("/{slug}/diff", response_model=DiffResponse)
async def diff_versions(
    slug: str,
    from_version: int = Query(..., alias="from"),
    to_version: int = Query(..., alias="to"),
    branch: str = "main",
    registry: PromptRegistry = Depends(get_registry),
    vcs: VersionControl = Depends(get_vcs),
) -> DiffResponse:
    """Get structural diff between two versions."""
    prompt = registry.get_prompt(slug)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{slug}' not found")

    prompt_id = str(prompt["id"])
    v_from = vcs.get_version(prompt_id=prompt_id, version=from_version, branch=branch)
    v_to = vcs.get_version(prompt_id=prompt_id, version=to_version, branch=branch)

    if not v_from or not v_to:
        raise HTTPException(status_code=404, detail="One or both versions not found")

    differ = StructuralDiffer()
    diff = differ.diff(v_from["content"], v_to["content"])

    return DiffResponse(
        prompt_id=prompt["id"],
        from_version=from_version,
        to_version=to_version,
        changes=diff["changes"],
        summary=diff["summary"],
    )


@router.post("/{slug}/rollback", response_model=VersionResponse)
async def rollback_version(
    slug: str,
    data: RollbackRequest,
    registry: PromptRegistry = Depends(get_registry),
    vcs: VersionControl = Depends(get_vcs),
) -> VersionResponse:
    """Rollback to a previous version."""
    prompt = registry.get_prompt(slug)
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{slug}' not found")

    version = vcs.rollback(
        prompt_id=str(prompt["id"]),
        version=data.version,
        author=data.author,
    )
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {data.version} not found")
    return VersionResponse(**version)
