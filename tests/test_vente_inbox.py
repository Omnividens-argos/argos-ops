"""Tests inbox du pôle Vente (archi v2, S4) — tri + gate AI Act + draft."""

from __future__ import annotations

from pathlib import Path

import pytest

from argos_ops.poles.vente import inbox


def _write_messages(root: Path, body: str) -> None:
    d = root / "vente" / "inbox"
    d.mkdir(parents=True, exist_ok=True)
    (d / "messages.yaml").write_text(body, encoding="utf-8")


def test_classify_keywords() -> None:
    assert inbox.classify("Demande de devis", "vos tarifs ?") == "lead_chaud"
    assert inbox.classify("Bug", "le scan ne marche pas") == "sav"
    assert inbox.classify("Candidature spontanée", "mon CV") == "recrutement"
    assert inbox.classify("Gagnez du bitcoin", "casino loterie") == "spam"
    assert inbox.classify("Bonjour", "juste un mot") == "autre"


def test_load_and_category_override(tmp_path: Path) -> None:
    _write_messages(
        tmp_path,
        "messages:\n"
        "  - id: m1\n    from_email: a@b.fr\n    subject: Bug scan\n    body: ne marche pas\n"
        "    received_at: '2026-06-17'\n    category_override: lead_chaud\n",
    )
    msgs = inbox.load_messages(poles_root=tmp_path)
    assert msgs[0].category == "lead_chaud"  # override prioritaire


def test_human_requested_flag(tmp_path: Path) -> None:
    _write_messages(
        tmp_path,
        "messages:\n"
        "  - id: m1\n    from_email: dpo@x.fr\n    subject: Question\n"
        "    body: Merci de me repondre par un humain, pas de bot svp.\n    received_at: '2026-06-17'\n",
    )
    msg = inbox.load_messages(poles_root=tmp_path)[0]
    assert msg.human_requested is True


async def test_draft_reply_blocked_for_human(tmp_path: Path) -> None:
    _write_messages(
        tmp_path,
        "messages:\n"
        "  - id: m1\n    from_email: dpo@x.fr\n    subject: Q\n"
        "    body: parler a un humain svp\n    received_at: '2026-06-17'\n",
    )
    with pytest.raises(inbox.HumanResponseRequiredError):
        inbox.draft_reply("m1", poles_root=tmp_path)


def test_draft_reply_writes_and_flips_status(tmp_path: Path) -> None:
    _write_messages(
        tmp_path,
        "messages:\n"
        "  - id: m1\n    from_email: lead@x.fr\n    from_name: Lead\n    subject: Devis\n"
        "    body: vos tarifs svp\n    received_at: '2026-06-17'\n",
    )
    path = inbox.draft_reply("m1", poles_root=tmp_path)
    assert path is not None and path.exists()
    assert inbox.load_messages(poles_root=tmp_path)[0].status == "drafted"


def test_draft_reply_unknown(tmp_path: Path) -> None:
    _write_messages(tmp_path, "messages: []\n")
    assert inbox.draft_reply("nope", poles_root=tmp_path) is None
