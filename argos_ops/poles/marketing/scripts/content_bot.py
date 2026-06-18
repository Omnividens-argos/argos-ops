"""``ContentBotScript`` — publie les drafts validés & échus (Marketing, archi v2).

Porté de l'esprit de ``argos_ops.agents.content_bot`` mais **local-first** et
self-contained au pôle : le script scanne la file de drafts
(:mod:`argos_ops.poles.marketing.drafts`), retient ceux qui sont ``validated`` et
dont ``scheduled_for`` est échu, les marque ``published`` et **écrit un fait de
publication** dans sa mémoire (``kind="publication"``). Aucune API tierce, aucun
Discord, aucune DB (D-017) : le posting réel sur LinkedIn/Mastodon/… reste géré
par les connecteurs ``argos_ops.social`` quand les tokens sont présents — ici on
journalise la décision de publication (mode shadow par défaut).

Idempotent : une fois ``published``, un draft n'est plus repris ; et l'écriture
mémoire déduplique par hash de corps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.marketing.channels import get_channel
from argos_ops.poles.marketing.drafts import find_publishable, mark_published


class ContentBotScript(BaseScript):
    """Publie (shadow) les drafts validés échus et mémorise chaque publication."""

    pole = "marketing"
    name = "content_bot"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        now: datetime | None = None,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._now = now

    async def run(self) -> ScriptResult:
        now = self._now or datetime.now(UTC)
        ready = find_publishable(now, poles_root=self.poles_root)

        written = []
        for draft in ready:
            channel = get_channel(draft.channel)
            label = channel.label if channel else draft.channel
            # On écrit le fait de publication AVANT de basculer le statut : si le
            # mark échoue, le draft reste ``validated`` et le prochain run réécrit
            # le même fait (idempotent par hash) puis re-marque — auto-réparation,
            # zéro fait de publication perdu (l'inverse perdrait l'audit shadow).
            record = await self.write_memory(
                f"Publié (shadow) sur {label} : {draft.title}",
                kind="publication",
                tags=(draft.channel, "shadow"),
                source=draft.id,
                created_at=draft.scheduled_for,
            )
            mark_published(draft.id, poles_root=self.poles_root)
            written.append(record)

        return ScriptResult(
            status="success",
            summary=f"{len(written)} draft(s) publié(s) (shadow) sur {len(ready)} échu(s)",
            written=written,
        )


__all__ = ["ContentBotScript"]
