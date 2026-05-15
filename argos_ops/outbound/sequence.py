"""IO séquences outbound — lecture CSV inbox + scaffold dossiers (P13).

Discipline D-017 : tout est local-first, file-system. Pas de DB pour
les séquences en P13.A — c'est volontaire pour rester debug-friendly et
inspectable par le fondateur (il peut grep, ouvrir dans un éditeur,
versionner localement). Quand P13.B (live mode) arrivera, on pourra
miroirer l'état dans Postgres via une vue agrégée si besoin de stats
historiques.

Arborescence cible (créée à la première écriture) :

::

    data/outbound/
    ├── inbox/                  # CSVs déposés par le fondateur
    │   └── leads.csv
    ├── enriched/               # output skill lead-enricher
    │   └── <slug>.md
    └── sequences/              # output scaffold/draft-outbound
        └── <slug>/
            ├── meta.yaml       # SequenceState sérialisé
            ├── touch_1.md      # placeholder ou drafted
            ├── touch_2.md
            ├── ...
            └── touch_5.md
"""

from __future__ import annotations

import csv
import re
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from argos_ops.config import REPO_ROOT
from argos_ops.outbound.models import LeadInput, SequenceState, Touch, TouchStep
from argos_ops.outbound.templates import compute_touch_dates, generate_opt_out_token, slugify

# =============================================================================
# Chemins canoniques
# =============================================================================
OUTBOUND_ROOT: Path = REPO_ROOT / "data" / "outbound"
INBOX_DIR: Path = OUTBOUND_ROOT / "inbox"
ENRICHED_DIR: Path = OUTBOUND_ROOT / "enriched"
SEQUENCES_DIR: Path = OUTBOUND_ROOT / "sequences"


# =============================================================================
# CSV inbox — parsing strict
# =============================================================================
_REQUIRED_COLS = {"full_name", "domain"}
_OPTIONAL_COLS = {"title_hint", "linkedin_url"}
_ALL_COLS = _REQUIRED_COLS | _OPTIONAL_COLS

# Domaine = au moins un point, TLD 2-63 chars (RFC compliant simplified)
_DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,63}$")


def read_inbox_csv(path: Path) -> list[LeadInput]:
    """Lit un CSV de leads et retourne la liste validée.

    Raises:
        FileNotFoundError: si ``path`` n'existe pas.
        ValueError: si l'en-tête manque les colonnes obligatoires, ou si
            une ligne a un domaine syntaxiquement invalide. Le but est
            d'échouer tôt — un CSV mal formé peut générer 200 séquences
            poubelle sinon.

    Note : les lignes vides ou commençant par ``#`` sont ignorées
    (permet de commenter le CSV temporairement).
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV inbox introuvable : {path}")

    leads: list[LeadInput] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV {path} sans en-tête")
        header = {h.strip().lower() for h in reader.fieldnames}
        missing = _REQUIRED_COLS - header
        if missing:
            raise ValueError(f"CSV {path} : colonnes manquantes {missing}")
        extra = header - _ALL_COLS
        if extra:
            raise ValueError(f"CSV {path} : colonnes inconnues {extra} (autorisées : {_ALL_COLS})")

        for line_num, row in enumerate(reader, start=2):
            full_name = (row.get("full_name") or "").strip()
            domain = (row.get("domain") or "").strip().lower()
            if not full_name or full_name.startswith("#"):
                continue
            if not domain:
                raise ValueError(f"CSV {path} ligne {line_num} : domain vide")
            if not _DOMAIN_RE.match(domain):
                raise ValueError(f"CSV {path} ligne {line_num} : domain '{domain}' invalide")
            title_hint = (row.get("title_hint") or "").strip() or None
            linkedin_url = (row.get("linkedin_url") or "").strip() or None
            leads.append(
                LeadInput(
                    full_name=full_name,
                    domain=domain,
                    title_hint=title_hint,
                    linkedin_url=linkedin_url,
                )
            )
    return leads


# =============================================================================
# Scaffold — création des dossiers et fichiers d'une séquence
# =============================================================================
def is_sequence_scaffolded(slug: str, *, root: Path = SEQUENCES_DIR) -> bool:
    """``True`` si ``<root>/<slug>/meta.yaml`` existe."""
    return (root / slug / "meta.yaml").exists()


def scaffold_sequence_dir(
    lead: LeadInput,
    *,
    secret: str,
    start_date: date | None = None,
    root: Path = SEQUENCES_DIR,
    enriched_root: Path = ENRICHED_DIR,
) -> Path:
    """Crée le dossier d'une séquence pour un lead et retourne son chemin.

    Idempotent : si ``meta.yaml`` existe déjà, retourne le chemin
    existant sans rien écraser. Permet au cron de re-tourner sur le même
    CSV sans dupliquer les séquences.

    Génère :

    - ``meta.yaml`` — sérialisation de ``SequenceState``
    - ``touch_1.md`` à ``touch_5.md`` — placeholders avec frontmatter

    Le ``body`` de chaque touch est intentionnellement vide (``null``) —
    le slash command ``/draft-outbound`` viendra remplir via les skills
    ``lead-enricher`` + ``outbound-personalizer`` + futur ``outbound-drafter``.
    """
    slug = slugify(lead.full_name, lead.domain)
    seq_dir = root / slug
    if (seq_dir / "meta.yaml").exists():
        return seq_dir

    seq_dir.mkdir(parents=True, exist_ok=True)
    today = start_date or datetime.now(UTC).date()
    cadence = compute_touch_dates(today)

    # On hash l'email *deviné* le plus probable pour le token initial —
    # le slash /draft-outbound pourra régénérer le token quand
    # lead-enricher aura fourni l'email final (firstname.lastname étant
    # le pattern majoritaire BtoB FR).
    probable_email = _probable_email(lead.full_name, lead.domain)
    opt_out_token = generate_opt_out_token(probable_email, secret)

    enriched_path = enriched_root / f"{slug}.md"

    touches: list[Touch] = []
    for step, sched_date in zip(TouchStep, cadence, strict=True):
        touches.append(Touch(step=step, scheduled_date=sched_date, status="scaffold"))

    state = SequenceState(
        lead_slug=slug,
        full_name=lead.full_name,
        domain=lead.domain,
        enriched_path=str(enriched_path.relative_to(REPO_ROOT))
        if enriched_root == ENRICHED_DIR
        else str(enriched_path),
        opt_out_token=opt_out_token,
        sequence_status="scaffold",
        touches=touches,
        created_at=datetime.now(UTC).isoformat(),
    )

    _write_meta(seq_dir / "meta.yaml", state)
    for touch in touches:
        _write_touch_placeholder(seq_dir / f"touch_{touch.step.value}.md", touch, lead)

    return seq_dir


def _probable_email(full_name: str, domain: str) -> str:
    """Devine ``firstname.lastname@domain`` — fallback déterministe.

    Utilisé uniquement pour pré-calculer un token d'opt-out à
    scaffold-time. Le skill ``lead-enricher`` produit ensuite des
    guesses scorés qui peuvent remplacer celui-ci au moment de
    ``/draft-outbound``.
    """
    parts = re.split(r"\s+", full_name.strip().lower())
    if len(parts) >= 2:
        local = f"{parts[0]}.{parts[-1]}"
    elif parts:
        local = parts[0]
    else:
        local = "unknown"
    local = re.sub(r"[^a-z0-9.]", "", local)
    return f"{local}@{domain}"


def _write_meta(path: Path, state: SequenceState) -> None:
    """Sérialise SequenceState → meta.yaml humain-friendly."""
    payload = {
        "lead_slug": state.lead_slug,
        "full_name": state.full_name,
        "domain": state.domain,
        "enriched_path": state.enriched_path,
        "opt_out_token": state.opt_out_token,
        "sequence_status": state.sequence_status,
        "created_at": state.created_at,
        "notes": state.notes,
        "touches": [
            {
                "step": int(t.step),
                "scheduled_date": t.scheduled_date.isoformat(),
                "status": t.status,
                "subject": t.subject,
                "body": t.body,
                "judge_score": t.judge_score,
                "judge_verdict": t.judge_verdict,
                "sent_at": t.sent_at,
            }
            for t in state.touches
        ],
    }
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


_TOUCH_LABELS: dict[TouchStep, str] = {
    TouchStep.DISCOVERY: "Discovery (D+0) — opener personnalisé + 1 question",
    TouchStep.VALUE: "Value (D+3) — drop de valeur (blog / mini-démo)",
    TouchStep.CASE: "Case (D+7) — étude de cas chiffrée",
    TouchStep.PROOF: "Proof (D+14) — preuve sociale / feature spécifique",
    TouchStep.BREAKUP: "Breakup (D+30) — break-up email court",
}


def _write_touch_placeholder(path: Path, touch: Touch, lead: LeadInput) -> None:
    """Écrit un touch_N.md vide avec frontmatter + guide skill.

    Le frontmatter sert de contrat avec `/draft-outbound` qui viendra
    remplir le body sans toucher au reste.
    """
    label = _TOUCH_LABELS[touch.step]
    content = (
        f"---\n"
        f"step: {int(touch.step)}\n"
        f'step_label: "{label}"\n'
        f"scheduled_date: {touch.scheduled_date.isoformat()}\n"
        f"status: scaffold\n"
        f"subject: null\n"
        f"judge_score: null\n"
        f"judge_verdict: null\n"
        f"sent_at: null\n"
        f"---\n"
        f"\n"
        f"<!--\n"
        f"PLACEHOLDER scaffold — body à drafter via `/draft-outbound {slugify(lead.full_name, lead.domain)}`.\n"
        f"Le skill `outbound-drafter` (P13.A.+) ou drafting manuel produira le body ci-dessous.\n"
        f"Step : {label}\n"
        f"-->\n"
    )
    path.write_text(content, encoding="utf-8")


# =============================================================================
# Lecture d'une séquence existante
# =============================================================================
def load_sequence_state(slug: str, *, root: Path = SEQUENCES_DIR) -> SequenceState:
    """Charge meta.yaml et reconstruit un ``SequenceState``.

    Raises:
        FileNotFoundError: si la séquence n'existe pas.
        ValueError: si meta.yaml est corrompu.
    """
    meta_path = root / slug / "meta.yaml"
    if not meta_path.exists():
        raise FileNotFoundError(f"Séquence inconnue : {slug}")
    raw = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"meta.yaml corrompu pour {slug}")
    touches_raw = raw.get("touches") or []
    touches = [
        Touch(
            step=TouchStep(int(t["step"])),
            scheduled_date=date.fromisoformat(t["scheduled_date"]),
            status=t.get("status", "scaffold"),
            subject=t.get("subject"),
            body=t.get("body"),
            judge_score=t.get("judge_score"),
            judge_verdict=t.get("judge_verdict"),
            sent_at=t.get("sent_at"),
        )
        for t in touches_raw
    ]
    return SequenceState(
        lead_slug=raw["lead_slug"],
        full_name=raw["full_name"],
        domain=raw["domain"],
        enriched_path=raw.get("enriched_path"),
        opt_out_token=raw["opt_out_token"],
        sequence_status=raw.get("sequence_status", "scaffold"),
        touches=touches,
        created_at=raw.get("created_at", ""),
        notes=raw.get("notes"),
    )


__all__ = [
    "ENRICHED_DIR",
    "INBOX_DIR",
    "OUTBOUND_ROOT",
    "SEQUENCES_DIR",
    "is_sequence_scaffolded",
    "load_sequence_state",
    "read_inbox_csv",
    "scaffold_sequence_dir",
]
