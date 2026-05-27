"""Lecture / écriture des YAML de config externe depuis l'Admin Panel (Phase 2).

Whitelist stricte : seuls les chemins explicitement listés ici sont
accessibles. Empêche un client de l'API d'écrire dans `.env`, `.git`, etc.

Convention :
  - chemins relatifs au repo (``project_root()`` ci-dessous)
  - extensions autorisées : .yaml uniquement (.yml normalisé en .yaml côté projet)
  - validation YAML obligatoire avant écriture (refuse si pas parsable)
  - backup .bak.<timestamp> avant chaque écriture
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml
from fastapi import HTTPException
from loguru import logger

# Mapping bot_name → chemin YAML lisible/éditable depuis le panel.
# Source de vérité côté UI : ``frontend/src/lib/botMetadata.ts::BOT_METADATA``.
# Garder les deux alignés. Tout YAML ajouté côté front DOIT être listé ici
# sinon l'API renverra 403.
ALLOWED_CONFIG_FILES: dict[str, str] = {
    "UptimeMonitor": "data/uptime/endpoints.yaml",
    "BotConfigManager": "data/agent_config/baseline.yaml",
    "OrchestratorBot": "data/agent_config/baseline.yaml",
    "SecretRotator": "data/secrets/rotation_log.yaml",
    "OKRTracker": "data/okr/2026-Q2.example.yaml",
    "ReconcileBot": "data/finance/stripe_payouts.example.yaml",
    "BurnRateMonitor": "data/strategy/burn.example.yaml",
    "ProspectMiner": "data/sales/prospects/sources.example.yaml",
    "IntentSignalsBot": "data/sales/signals/sources.example.yaml",
    "ContractGenerator": "data/contracts/clients.example.yaml",
    "RGPDAuditor": "data/compliance/rgpd_registry.example.yaml",
    "SEOBot": "data/seo/keywords.yaml",
    "KeywordRadar": "data/seo/keywords.yaml",
    "ExpenseAuditor": "data/expenses/qonto_last.csv",  # CSV mais on le rendra read-only.
}

# Limite hard pour éviter les abus (DoS via gros payload).
MAX_FILE_SIZE_BYTES = 256 * 1024  # 256 KB largement suffisant pour un YAML de config.


def project_root() -> Path:
    """Racine du repo (parent de ``argos_ops/``)."""
    return Path(__file__).resolve().parents[2]


def _resolve_safe(rel_path: str) -> Path:
    """Résout ``rel_path`` sous ``project_root()`` en refusant tout escape (``..``)."""
    root = project_root().resolve()
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"Chemin hors repo : {rel_path}"
        ) from exc
    return target


def get_allowed_path(agent_name: str) -> Path:
    """Récupère le chemin résolu si l'agent a un YAML autorisé, sinon 403."""
    rel = ALLOWED_CONFIG_FILES.get(agent_name)
    if rel is None:
        raise HTTPException(
            status_code=403,
            detail=f"Aucun fichier de config externe autorisé pour {agent_name}",
        )
    return _resolve_safe(rel)


def read_config_file(agent_name: str) -> tuple[str, str, bool]:
    """Retourne ``(rel_path, raw_text, exists)`` pour le bot demandé.

    Le booléen ``exists`` permet à l'UI d'afficher "fichier absent" sans 404
    dur (utile pour les ``.example.yaml`` qui n'ont pas encore été dupliqués
    en version réelle).
    """
    rel = ALLOWED_CONFIG_FILES[agent_name]
    path = get_allowed_path(agent_name)
    if not path.exists():
        return rel, "", False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Lecture échouée : {exc}") from exc
    if len(text.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Fichier trop volumineux pour édition in-panel (> 256 KB).",
        )
    return rel, text, True


def write_config_file(agent_name: str, new_text: str) -> tuple[str, str]:
    """Écrit ``new_text`` après validation YAML + backup .bak.<timestamp>.

    Refuse :
      - chemins .csv (read-only par défaut)
      - payload > MAX_FILE_SIZE_BYTES
      - YAML qui ne parse pas (sauvegarde une copie partielle = trop risqué)
    """
    path = get_allowed_path(agent_name)
    if path.suffix.lower() != ".yaml":
        raise HTTPException(
            status_code=400,
            detail=f"Édition refusée — {path.suffix} non éditable depuis le panel.",
        )
    encoded = new_text.encode("utf-8")
    if len(encoded) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Payload > {MAX_FILE_SIZE_BYTES} octets — limite panel dépassée.",
        )

    # Validation YAML
    try:
        yaml.safe_load(new_text)
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"YAML invalide : {exc}",
        ) from exc

    # Backup
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        backup = path.with_suffix(path.suffix + f".bak.{timestamp}")
        try:
            shutil.copy2(path, backup)
        except OSError as exc:
            logger.warning("yaml_config: backup failed for {} → {}", path, exc)

    path.write_text(new_text, encoding="utf-8")
    logger.info("yaml_config: {} ({}) updated via panel", agent_name, path.name)
    rel = ALLOWED_CONFIG_FILES[agent_name]
    return rel, new_text


def validate_yaml(text: str) -> tuple[bool, str | None]:
    """Validation pure (pas d'I/O) — utilisée pour le bouton « Test syntaxe »."""
    try:
        yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return False, str(exc)
    return True, None


__all__ = [
    "ALLOWED_CONFIG_FILES",
    "get_allowed_path",
    "read_config_file",
    "validate_yaml",
    "write_config_file",
]
