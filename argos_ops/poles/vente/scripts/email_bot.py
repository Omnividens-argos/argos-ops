"""``EmailBotScript`` — tri de l'inbox entrante (Vente, archi v2, S4).

Bras déterministe : lit ``data/poles/vente/inbox/messages.yaml``, **classe** chaque
message non archivé par mots-clés (:func:`argos_ops.poles.vente.inbox.classify`) et
écrit un fait par message actionnable dans sa mémoire (``kind="inbound"``). Le spam
est compté mais non mémorisé (bruit). Un message qui demande une réponse humaine
est marqué (``tags`` ``human_requested`` + ``critical``) pour que le ``VenteAgent``
le route en file humaine — Python tranche, aucun drafting IA (AI Act).

Pas de Discord, pas d'IMAP, pas de LLM ici (D-017) : l'ingestion IMAP réelle (D-018)
viendra remplir ``messages.yaml`` ; ce script ne fait que trier et mémoriser.
Idempotent : même inbox ⇒ mêmes faits.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente import inbox
from argos_ops.poles.vente.inbox import HOT_CATEGORIES


class EmailBotScript(BaseScript):
    """Trie l'inbox et mémorise les messages actionnables (``kind="inbound"``)."""

    pole = "vente"
    name = "email_bot"

    def __init__(self, *, poles_root: Path = POLES_DIR) -> None:
        super().__init__(poles_root=poles_root)

    async def run(self) -> ScriptResult:
        messages = inbox.load_messages(poles_root=self.poles_root)
        if not messages:
            return ScriptResult(
                status="success",
                summary="Inbox vide (data/poles/vente/inbox/messages.yaml) — rien à trier.",
                written=[],
            )

        written = []
        by_category: dict[str, int] = {}
        spam = 0
        human = 0
        for msg in messages:
            if msg.status == "archived":
                continue
            category = msg.category
            by_category[category] = by_category.get(category, 0) + 1
            if category == "spam":
                spam += 1
                continue  # bruit : compté mais non mémorisé

            tags: tuple[str, ...] = (category,)
            human_requested = msg.human_requested
            if human_requested:
                human += 1
                tags = (*tags, "human_requested", "critical")
            important = human_requested or category in HOT_CATEGORIES
            record = await self.write_memory(
                f"Inbound [{category}] de {msg.from_name or '?'} <{msg.from_email}> : {msg.subject}",
                kind="inbound",
                tags=tags,
                important=important,
                source=msg.from_email or self.name,
            )
            written.append(record)

        leads = by_category.get("lead_chaud", 0)
        return ScriptResult(
            status="success",
            summary=(
                f"{len(messages)} message(s) trié(s) — {leads} lead(s) chaud(s), "
                f"{human} réponse(s) humaine(s) requise(s), {spam} spam"
            ),
            written=written,
        )


__all__ = ["EmailBotScript"]
