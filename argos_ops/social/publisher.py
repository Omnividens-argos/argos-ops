"""Orchestration publication ContentBot (P11).

Lit les drafts validés (``status: validated`` + ``scheduled_for`` <= now)
sous ``data/content/drafts/``, dispatch vers le bon connecteur selon
``channel:``, et déplace le draft vers ``data/content/published/`` avec
URL publique + timestamp publication.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.social.linkedin import LinkedInClient
from argos_ops.social.mastodon import MastodonClient

DRAFTS_DIR = REPO_ROOT / "data" / "content" / "drafts"
PUBLISHED_DIR = REPO_ROOT / "data" / "content" / "published"


@dataclass
class PublishResult:
    """Résultat d'une tentative de publication d'un draft."""

    draft_path: Path
    status: str  # 'published' | 'shadow' | 'failed' | 'skipped'
    platform: str
    url: str | None
    error: str | None


def _split_frontmatter(content: str) -> tuple[dict[str, object], str]:
    """Parse un fichier markdown avec frontmatter YAML."""
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    fm = yaml.safe_load(content[4:end]) or {}
    body = content[end + 5 :]
    return (fm if isinstance(fm, dict) else {}), body


def _join_frontmatter(fm: dict[str, object], body: str) -> str:
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n" + body


def find_ready_drafts(now: datetime | None = None) -> list[Path]:
    """Retourne les drafts dont status=validated et scheduled_for <= now."""
    now = now or datetime.now(UTC)
    if not DRAFTS_DIR.exists():
        return []
    ready: list[Path] = []
    for path in sorted(DRAFTS_DIR.rglob("*.md")):
        try:
            fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            logger.warning(f"Draft {path.name} illisible : {exc}")
            continue
        if fm.get("status") != "validated":
            continue
        scheduled = fm.get("scheduled_for")
        if scheduled is None:
            continue
        if isinstance(scheduled, str):
            try:
                scheduled_dt = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
            except ValueError:
                continue
        elif isinstance(scheduled, datetime):
            scheduled_dt = scheduled
        else:
            continue
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=UTC)
        if scheduled_dt <= now:
            ready.append(path)
    return ready


async def publish_draft(
    draft_path: Path,
    *,
    linkedin: LinkedInClient | None = None,
    mastodon: MastodonClient | None = None,
    dry_run: bool = False,
) -> PublishResult:
    """Publie un draft sur le canal indiqué par son frontmatter."""
    content = draft_path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(content)
    channel = str(fm.get("channel", "")).lower()
    text = body.strip()

    if not text:
        return PublishResult(draft_path, "failed", channel, None, "body vide")

    if channel == "linkedin":
        client = linkedin or _default_linkedin()
        result = await client.post(text, dry_run=dry_run)
    elif channel == "mastodon":
        client_m = mastodon or _default_mastodon()
        result = await client_m.post(text, dry_run=dry_run)
    else:
        return PublishResult(draft_path, "failed", channel, None, f"channel inconnu : {channel}")

    pub = PublishResult(
        draft_path=draft_path,
        status=str(result.get("status") or "failed"),
        platform=str(result.get("platform") or channel),
        url=result.get("url") if isinstance(result.get("url"), str) else None,  # type: ignore[arg-type]
        error=result.get("error") if isinstance(result.get("error"), str) else None,  # type: ignore[arg-type]
    )

    if pub.status in ("published", "shadow") and not dry_run:
        _move_to_published(draft_path, fm, body, pub)

    return pub


def _move_to_published(
    draft_path: Path, fm: dict[str, object], body: str, pub: PublishResult
) -> None:
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    fm["status"] = "published" if pub.status == "published" else "published_shadow"
    fm["published_at"] = datetime.now(UTC).isoformat()
    if pub.url:
        fm["published_url"] = pub.url
    dest = PUBLISHED_DIR / draft_path.name
    dest.write_text(_join_frontmatter(fm, body), encoding="utf-8")
    try:
        draft_path.unlink()
    except OSError:
        shutil.move(str(draft_path), str(dest))


def _default_linkedin() -> LinkedInClient:
    settings = get_settings()
    return LinkedInClient(
        api_token=settings.linkedin_api_token,
        org_urn=settings.linkedin_org_urn,
    )


def _default_mastodon() -> MastodonClient:
    settings = get_settings()
    return MastodonClient(
        instance_url=settings.mastodon_instance_url,
        access_token=settings.mastodon_access_token,
    )


__all__ = ["DRAFTS_DIR", "PUBLISHED_DIR", "PublishResult", "find_ready_drafts", "publish_draft"]
