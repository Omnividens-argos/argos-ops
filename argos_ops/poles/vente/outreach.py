"""Outbound du pôle Vente (archi v2, S4) — leads, enrichissement, séquences, Bloctel.

Réutilise les briques pures existantes :

- :func:`argos_ops.sales.enrichment.enrich_lead` (email/persona/BANT, offline) ;
- :mod:`argos_ops.outbound.sequence` (CSV inbox, scaffold de séquences 5-touches) ;
- :func:`argos_ops.compliance.is_phone_on_bloctel` + :func:`normalize_phone_fr`.

**Garde-fou central du pôle (« Python tranche »)** : la conformité Bloctel +
l'éligibilité RGPD bornent l'outbound. :func:`build_bloctel_report` arme une
alerte (liste périmée > 35j ou téléphone opposé trouvé) ⇒ l'outbound est **gelé**
(:func:`outbound_frozen`). :func:`eligibility` disqualifie un lead à email perso
ou BANT < 40. C'est l'analogue du breaker ``ad_spend_runaway`` du pôle Pub : le
``VenteAgent`` propose, mais ne peut jamais lever ce gel.

100 % fichiers / local-first (D-017). Mode shadow : aucun envoi réel.
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from loguru import logger

from argos_ops.compliance import is_phone_on_bloctel, normalize_phone_fr
from argos_ops.outbound.models import LeadInput, SequenceState
from argos_ops.outbound.sequence import (
    is_sequence_scaffolded,
    load_sequence_state,
    read_inbox_csv,
    scaffold_sequence_dir,
)
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.vente.store import read_markdown, write_markdown
from argos_ops.sales.enrichment import enrich_lead

VENTE_POLE = "vente"

# Seuil de qualification BANT (aligné /draft-outbound P13.A) + délai de péremption
# de la liste Bloctel mensuelle (au-delà, la liste manque le refresh du mois).
BANT_QUALIFIED_MIN = 40
BLOCTEL_STALE_DAYS = 35

# Domaines email grand-public : un lead « pro » sur l'un d'eux est disqualifié
# (intérêt légitime BtoB non démontrable — RGPD art. 6.1.f).
PERSONAL_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.fr",
        "hotmail.com",
        "hotmail.fr",
        "outlook.com",
        "outlook.fr",
        "live.fr",
        "live.com",
        "free.fr",
        "orange.fr",
        "sfr.fr",
        "wanadoo.fr",
        "laposte.net",
        "icloud.com",
        "me.com",
        "gmx.com",
        "proton.me",
        "protonmail.com",
        "aol.com",
    }
)


# =============================================================================
# Chemins
# =============================================================================
def outbound_root(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / VENTE_POLE / "outbound"


def inbox_csv_path(*, poles_root: Path = POLES_DIR) -> Path:
    return outbound_root(poles_root=poles_root) / "inbox" / "leads.csv"


def enriched_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return outbound_root(poles_root=poles_root) / "enriched"


def sequences_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return outbound_root(poles_root=poles_root) / "sequences"


def bloctel_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / VENTE_POLE / "compliance" / "bloctel"


def lead_phones_path(*, poles_root: Path = POLES_DIR) -> Path:
    """CSV ``identifier,phone`` (séparé de leads.csv qui a un schéma strict)."""
    return poles_root / VENTE_POLE / "compliance" / "lead_phones.csv"


def _shadow_secret() -> str:
    """Secret HMAC opt-out (shadow). En live (P13.B) vient de l'env, jamais en dur."""
    return os.environ.get("OUTBOUND_UNSUBSCRIBE_SECRET", "argos-ops-shadow-secret")


# =============================================================================
# Leads + enrichissement
# =============================================================================
@dataclass(frozen=True)
class EnrichedLead:
    """Fiche lead enrichie sérialisée dans ``enriched/<slug>.md``."""

    slug: str
    full_name: str
    domain: str
    title_hint: str | None
    persona: str
    bant_total: int
    qualified: bool
    best_email: str | None
    eligible: bool
    eligibility_reason: str


@dataclass(frozen=True)
class BantBreakdown:
    """Sous-scores BANT explicables (0-100 chacun, total borné à 100)."""

    budget: int
    authority: int
    need: int
    timing: int
    total: int


@dataclass(frozen=True)
class EmailGuessView:
    """Un candidat email pro deviné, avec son pattern et sa confidence."""

    email: str
    pattern: str
    confidence: int


@dataclass(frozen=True)
class LeadDetail:
    """Fiche enrichie complète d'un lead pour le panneau détail du cockpit.

    Réunit la fiche :class:`EnrichedLead` (résumé) + les champs structurés
    issus de l'enrichissement (breakdown BANT, signaux persona, guesses email)
    + le corps markdown de ``enriched/<slug>.md`` s'il a été écrit (``""`` sinon —
    la fiche reste calculable à chaud sans fichier).
    """

    lead: EnrichedLead
    persona_score: int
    persona_signals: tuple[str, ...]
    bant: BantBreakdown
    email_guesses: tuple[EmailGuessView, ...]
    markdown_body: str


# Domaine = au moins un point, TLD 2-63 chars (aligné sur outbound.sequence).
_DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,63}$")
_CSV_HEADER = ("full_name", "domain", "title_hint", "linkedin_url")


def load_leads(*, poles_root: Path = POLES_DIR) -> list[LeadInput]:
    """Lit le CSV inbox des leads. Absent ⇒ ``[]`` (best-effort cockpit)."""
    path = inbox_csv_path(poles_root=poles_root)
    if not path.exists():
        return []
    return read_inbox_csv(path)


def _existing_lead_keys(csv_path: Path) -> set[tuple[str, str]]:
    if not csv_path.exists():
        return set()
    keys: set[tuple[str, str]] = set()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            full = (row.get("full_name") or "").strip().lower()
            dom = (row.get("domain") or "").strip().lower()
            if full and not full.startswith("#"):
                keys.add((full, dom))
    return keys


def append_leads(
    leads: list[LeadInput], *, poles_root: Path = POLES_DIR
) -> tuple[list[LeadInput], int]:
    """Append des leads au CSV inbox (dédup ``(full_name, domain)`` + domaine valide).

    Retourne ``(ajoutés, ignorés)``. Crée le fichier (avec en-tête) au besoin.
    Réutilisé par l'upload CSV du cockpit et par ``ProspectMinerScript``.
    """
    csv_path = inbox_csv_path(poles_root=poles_root)
    existing = _existing_lead_keys(csv_path)
    added: list[LeadInput] = []
    skipped = 0
    for lead in leads:
        full = lead.full_name.strip()
        domain = lead.domain.strip().lower()
        if not full or not _DOMAIN_RE.match(domain):
            skipped += 1
            continue
        key = (full.lower(), domain)
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        added.append(
            LeadInput(
                full_name=full,
                domain=domain,
                title_hint=lead.title_hint,
                linkedin_url=lead.linkedin_url,
            )
        )
    if added:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not csv_path.exists()
        with csv_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_HEADER)
            if write_header:
                writer.writeheader()
            for lead in added:
                writer.writerow(
                    {
                        "full_name": lead.full_name,
                        "domain": lead.domain,
                        "title_hint": lead.title_hint or "",
                        "linkedin_url": lead.linkedin_url or "",
                    }
                )
    return added, skipped


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower() if "@" in email else ""


def is_personal_email(email: str | None) -> bool:
    """``True`` si l'email est sur un domaine grand-public."""
    return bool(email) and _email_domain(email or "") in PERSONAL_EMAIL_DOMAINS


def eligibility(*, best_email: str | None, bant_total: int) -> tuple[bool, str]:
    """Éligibilité outbound d'un lead (hors gel Bloctel global).

    Disqualifie, dans l'ordre : email indéterminable (nom ambigu → aucune adresse
    devinable) → email perso (RGPD) → BANT insuffisant. Un email manquant est un
    bloqueur dur : on ne lance jamais une séquence vers un contact qu'on ne peut
    pas adresser (« Python tranche »).
    """
    if not best_email:
        return False, "email non identifiable (nom ambigu — aucune adresse devinable)"
    if is_personal_email(best_email):
        return False, "email perso (intérêt légitime BtoB non démontrable — RGPD)"
    if bant_total < BANT_QUALIFIED_MIN:
        return False, f"BANT {bant_total} < {BANT_QUALIFIED_MIN} (pas assez qualifié)"
    return True, "qualifié"


def _compute_enriched(lead: LeadInput) -> tuple[EnrichedLead, dict[str, object]]:
    """Calcule l'enrichissement d'un lead (sans IO) → (fiche, data brute)."""
    from argos_ops.outbound.templates import slugify

    data = enrich_lead(full_name=lead.full_name, domain=lead.domain, title_hint=lead.title_hint)
    bant = data["bant"]
    assert isinstance(bant, dict)
    persona = data["persona"]
    assert isinstance(persona, dict)
    guesses = data["email_guesses"]
    assert isinstance(guesses, list)
    best_email = str(guesses[0]["email"]) if guesses else None
    bant_total = int(bant["total"])
    eligible, reason = eligibility(best_email=best_email, bant_total=bant_total)
    enriched = EnrichedLead(
        slug=slugify(lead.full_name, lead.domain),
        full_name=lead.full_name,
        domain=lead.domain,
        title_hint=lead.title_hint,
        persona=str(persona["name"]),
        bant_total=bant_total,
        qualified=bool(bant["is_qualified"]),
        best_email=best_email,
        eligible=eligible,
        eligibility_reason=reason,
    )
    return enriched, data


def enrich_view(lead: LeadInput) -> EnrichedLead:
    """Enrichit un lead **sans écrire** — vue cockpit live (offline, déterministe)."""
    return _compute_enriched(lead)[0]


def _detail_from_data(
    enriched: EnrichedLead, data: dict[str, object], *, markdown_body: str
) -> LeadDetail:
    """Assemble une :class:`LeadDetail` depuis la fiche + le dict brut d'enrichissement."""
    bant = data["bant"]
    assert isinstance(bant, dict)
    persona = data["persona"]
    assert isinstance(persona, dict)
    guesses = data["email_guesses"]
    assert isinstance(guesses, list)
    keywords = persona.get("matched_keywords") or []
    assert isinstance(keywords, list)
    return LeadDetail(
        lead=enriched,
        persona_score=int(persona["score"]),
        persona_signals=tuple(str(kw) for kw in keywords),
        bant=BantBreakdown(
            budget=int(bant["budget"]),
            authority=int(bant["authority"]),
            need=int(bant["need"]),
            timing=int(bant["timing"]),
            total=int(bant["total"]),
        ),
        email_guesses=tuple(
            EmailGuessView(
                email=str(g["email"]), pattern=str(g["pattern"]), confidence=int(g["confidence"])
            )
            for g in guesses
        ),
        markdown_body=markdown_body,
    )


def build_lead_detail(slug: str, *, poles_root: Path = POLES_DIR) -> LeadDetail | None:
    """Vue détail complète d'un lead par ``slug`` — ``None`` si le slug est inconnu.

    Recalcule l'enrichissement à chaud (offline, déterministe) pour exposer le
    breakdown BANT, les signaux persona et les guesses email, puis joint le corps
    markdown de ``enriched/<slug>.md`` s'il existe (``""`` sinon).
    """
    computed = next(
        (
            pair
            for lead in load_leads(poles_root=poles_root)
            if (pair := _compute_enriched(lead))[0].slug == slug
        ),
        None,
    )
    if computed is None:
        return None
    enriched, data = computed
    enriched_md = enriched_dir(poles_root=poles_root) / f"{slug}.md"
    markdown_body = ""
    if enriched_md.exists():
        try:
            _, markdown_body = read_markdown(enriched_md)
        except Exception as exc:  # best-effort — le détail reste calculable sans fichier
            logger.warning(
                f"outreach — enriched détail illisible {enriched_md} : {type(exc).__name__}: {exc}"
            )
    return _detail_from_data(enriched, data, markdown_body=markdown_body.strip())


def enrich_and_write(lead: LeadInput, *, poles_root: Path = POLES_DIR) -> EnrichedLead:
    """Enrichit un lead (email/persona/BANT) et écrit ``enriched/<slug>.md``.

    Idempotent au sens fichier : ré-écrit le même contenu pour un même lead.
    Branche les signaux d'achat (breach/CISO hire) plus tard via cross-pôle ; ici
    on score sur les seules données du CSV (offline).
    """
    enriched, data = _compute_enriched(lead)
    _write_enriched(enriched, data, poles_root=poles_root)
    return enriched


def _write_enriched(
    enriched: EnrichedLead, data: dict[str, object], *, poles_root: Path = POLES_DIR
) -> None:
    bant = data["bant"]
    assert isinstance(bant, dict)
    guesses = data["email_guesses"]
    assert isinstance(guesses, list)
    email_lines = "\n".join(
        f"- `{g['email']}` ({g['pattern']}, conf {g['confidence']})" for g in guesses
    )
    body = (
        f"# {enriched.full_name} — {enriched.domain}\n\n"
        f"**Persona ICP :** {enriched.persona}\n"
        f"**BANT :** {enriched.bant_total}/100 "
        f"(B {bant['budget']} · A {bant['authority']} · N {bant['need']} · T {bant['timing']})\n"
        f"**Éligible outbound :** {'oui' if enriched.eligible else 'NON'} — "
        f"{enriched.eligibility_reason}\n\n"
        f"## Emails probables\n{email_lines or '- (nom ambigu — pas de guess)'}\n"
    )
    write_markdown(
        enriched_dir(poles_root=poles_root) / f"{enriched.slug}.md",
        {
            "slug": enriched.slug,
            "full_name": enriched.full_name,
            "domain": enriched.domain,
            "title_hint": enriched.title_hint,
            "persona": enriched.persona,
            "bant_total": enriched.bant_total,
            "qualified": enriched.qualified,
            "best_email": enriched.best_email,
            "eligible": enriched.eligible,
            "eligibility_reason": enriched.eligibility_reason,
        },
        body=body,
    )


def load_enriched(*, poles_root: Path = POLES_DIR) -> list[EnrichedLead]:
    """Charge toutes les fiches enrichies (ordre alphabétique). Best-effort."""
    d = enriched_dir(poles_root=poles_root)
    if not d.exists():
        return []
    out: list[EnrichedLead] = []
    for path in sorted(d.glob("*.md")):
        try:
            fm, _ = read_markdown(path)
            out.append(
                EnrichedLead(
                    slug=str(fm.get("slug") or path.stem),
                    full_name=str(fm.get("full_name", "")),
                    domain=str(fm.get("domain", "")),
                    title_hint=(str(fm["title_hint"]) if fm.get("title_hint") else None),
                    persona=str(fm.get("persona", "unknown")),
                    bant_total=int(str(fm.get("bant_total", 0) or 0)),
                    qualified=bool(fm.get("qualified", False)),
                    best_email=(str(fm["best_email"]) if fm.get("best_email") else None),
                    eligible=bool(fm.get("eligible", False)),
                    eligibility_reason=str(fm.get("eligibility_reason", "")),
                )
            )
        except Exception as exc:  # best-effort
            logger.warning(f"outreach — enriched illisible {path} : {type(exc).__name__}: {exc}")
    return out


# =============================================================================
# Séquences outbound (scaffold + lecture)
# =============================================================================
def load_sequences(*, poles_root: Path = POLES_DIR) -> list[SequenceState]:
    """Charge l'état de toutes les séquences scaffoldées. Best-effort."""
    root = sequences_dir(poles_root=poles_root)
    if not root.exists():
        return []
    out: list[SequenceState] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "meta.yaml").exists():
            try:
                out.append(load_sequence_state(child.name, root=root))
            except (ValueError, KeyError) as exc:
                logger.warning(f"outreach — séquence illisible {child} : {exc}")
    return out


def scaffold_for_lead(lead: LeadInput, *, poles_root: Path = POLES_DIR) -> Path:
    """Scaffold une séquence 5-touches pour un lead (idempotent, mode shadow)."""
    return scaffold_sequence_dir(
        lead,
        secret=_shadow_secret(),
        root=sequences_dir(poles_root=poles_root),
        enriched_root=enriched_dir(poles_root=poles_root),
    )


def is_scaffolded(slug: str, *, poles_root: Path = POLES_DIR) -> bool:
    return is_sequence_scaffolded(slug, root=sequences_dir(poles_root=poles_root))


# =============================================================================
# Bloctel — le garde-fou conformité
# =============================================================================
@dataclass(frozen=True)
class BloctelMatch:
    identifier: str
    phone: str


@dataclass(frozen=True)
class BloctelReport:
    """Photo de conformité Bloctel — pilote le gel de l'outbound."""

    list_path: str | None
    list_age_days: int | None
    checked: int
    matches: tuple[BloctelMatch, ...]
    stale: bool
    should_alert: bool
    summary: str


def latest_bloctel_list(*, poles_root: Path = POLES_DIR) -> Path | None:
    """Dernier fichier ``bloctel_YYYY-MM.txt`` (par nom décroissant). ``None`` si aucun."""
    d = bloctel_dir(poles_root=poles_root)
    if not d.exists():
        return None
    candidates = sorted(d.glob("bloctel_*.txt"), reverse=True)
    return candidates[0] if candidates else None


def _list_age_days(list_path: Path, *, today: date) -> int | None:
    """Âge en jours depuis le 1er du mois encodé dans ``bloctel_YYYY-MM.txt``."""
    stem = list_path.stem  # bloctel_2026-06
    try:
        ym = stem.split("bloctel_", 1)[1]
        year_s, month_s = ym.split("-")
        anchor = date(int(year_s), int(month_s), 1)
    except (IndexError, ValueError):
        return None
    return (today - anchor).days


def load_lead_phones(*, poles_root: Path = POLES_DIR) -> list[tuple[str, str]]:
    """Charge ``compliance/lead_phones.csv`` → ``[(identifier, phone), ...]``.

    Colonnes acceptées : ``identifier`` (ou ``id``/``lead``) + ``phone`` (ou
    ``telephone``/``mobile``). Lignes vides / ``#`` ignorées. Absent ⇒ ``[]``.
    """
    path = lead_phones_path(poles_root=poles_root)
    if not path.exists():
        return []
    out: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        cols = {h.strip().lower(): h for h in reader.fieldnames}
        id_col = cols.get("identifier") or cols.get("id") or cols.get("lead")
        phone_col = cols.get("phone") or cols.get("telephone") or cols.get("mobile")
        if phone_col is None:
            return []
        for row in reader:
            phone = (row.get(phone_col) or "").strip()
            identifier = (row.get(id_col) or "").strip() if id_col else ""
            if not phone or phone.startswith("#"):
                continue
            out.append((identifier or phone, phone))
    return out


def build_bloctel_report(
    *, poles_root: Path = POLES_DIR, today: date | None = None
) -> BloctelReport:
    """Croise les téléphones leads avec la liste Bloctel → rapport de conformité.

    Alerte (``should_alert=True``) si la liste est absente / périmée (> 35j) **ou**
    si au moins un téléphone est opposé. C'est cette alerte qui gèle l'outbound.
    """
    today = today or date.today()
    list_path = latest_bloctel_list(poles_root=poles_root)
    phones = load_lead_phones(poles_root=poles_root)

    # Bloctel ne gouverne que le démarchage TÉLÉPHONIQUE (loi BtoC 2014) : sans
    # téléphone à vérifier, la liste est hors-sujet — on ne gèle pas l'outbound
    # email. C'est seulement quand on a des numéros qu'une liste absente/périmée
    # devient un risque de conformité (et donc un gel).
    if not phones:
        return BloctelReport(
            list_path=str(list_path.name) if list_path else None,
            list_age_days=_list_age_days(list_path, today=today) if list_path else None,
            checked=0,
            matches=(),
            stale=False,
            should_alert=False,
            summary="Aucun téléphone à vérifier — Bloctel non applicable (outbound email).",
        )

    if list_path is None:
        return BloctelReport(
            list_path=None,
            list_age_days=None,
            checked=len(phones),
            matches=(),
            stale=True,
            should_alert=True,
            summary=f"{len(phones)} téléphone(s) mais aucune liste Bloctel — outbound gelé.",
        )

    age = _list_age_days(list_path, today=today)
    stale = age is None or age > BLOCTEL_STALE_DAYS
    matches = tuple(
        BloctelMatch(identifier=ident, phone=normalize_phone_fr(phone) or phone)
        for ident, phone in phones
        if is_phone_on_bloctel(phone, bloctel_list_path=list_path)
    )
    should_alert = stale or bool(matches)
    if matches:
        summary = f"{len(matches)} téléphone(s) sur Bloctel — outbound gelé pour ces leads."
    elif age is None:
        summary = f"Nom de liste Bloctel illisible ({list_path.name}) — outbound gelé."
    elif stale:
        summary = f"Liste Bloctel périmée ({age}j > {BLOCTEL_STALE_DAYS}j) — outbound gelé."
    else:
        summary = f"{len(phones)} téléphone(s) vérifié(s), aucun sur Bloctel (liste {age}j)."
    return BloctelReport(
        list_path=str(list_path.name),
        list_age_days=age,
        checked=len(phones),
        matches=matches,
        stale=stale,
        should_alert=should_alert,
        summary=summary,
    )


def outbound_frozen(*, poles_root: Path = POLES_DIR, today: date | None = None) -> bool:
    """``True`` si l'outbound doit être gelé (conformité Bloctel non garantie)."""
    return build_bloctel_report(poles_root=poles_root, today=today).should_alert


__all__ = [
    "BANT_QUALIFIED_MIN",
    "BLOCTEL_STALE_DAYS",
    "PERSONAL_EMAIL_DOMAINS",
    "BantBreakdown",
    "BloctelMatch",
    "BloctelReport",
    "EmailGuessView",
    "EnrichedLead",
    "LeadDetail",
    "append_leads",
    "bloctel_dir",
    "build_bloctel_report",
    "build_lead_detail",
    "eligibility",
    "enrich_and_write",
    "enrich_view",
    "enriched_dir",
    "inbox_csv_path",
    "is_personal_email",
    "is_scaffolded",
    "latest_bloctel_list",
    "lead_phones_path",
    "load_enriched",
    "load_lead_phones",
    "load_leads",
    "load_sequences",
    "outbound_frozen",
    "outbound_root",
    "scaffold_for_lead",
    "sequences_dir",
]
