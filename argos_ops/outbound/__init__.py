"""OutboundBot — séquences cold email BtoB (P13, shadow mode).

D-017 : plomberie Python pure ici (templates, cadence, opt-out HMAC,
IO sequence state). Le drafting des bodies passe par Claude Code +
skills `lead-enricher` / `outbound-personalizer` / `outbound-drafter`
(futur) via le slash command `/draft-outbound`.

Mode shadow strict tant que `OUTBOUND_LIVE_MODE=false` (défaut) ET
domaine secondaire pas branché. Cf. plan P13 § 13.2 délivrabilité.
"""

from argos_ops.outbound.models import LeadInput, SequenceState, Touch, TouchStep
from argos_ops.outbound.sequence import (
    ENRICHED_DIR,
    INBOX_DIR,
    SEQUENCES_DIR,
    is_sequence_scaffolded,
    load_sequence_state,
    read_inbox_csv,
    scaffold_sequence_dir,
)
from argos_ops.outbound.templates import (
    OUTBOUND_FOOTER_TEMPLATE,
    TOUCH_CADENCE_DAYS,
    build_footer,
    build_opt_out_url,
    compute_touch_dates,
    generate_opt_out_token,
    slugify,
    verify_opt_out_token,
)

__all__ = [
    "ENRICHED_DIR",
    "INBOX_DIR",
    "OUTBOUND_FOOTER_TEMPLATE",
    "SEQUENCES_DIR",
    "TOUCH_CADENCE_DAYS",
    "LeadInput",
    "SequenceState",
    "Touch",
    "TouchStep",
    "build_footer",
    "build_opt_out_url",
    "compute_touch_dates",
    "generate_opt_out_token",
    "is_sequence_scaffolded",
    "load_sequence_state",
    "read_inbox_csv",
    "scaffold_sequence_dir",
    "slugify",
    "verify_opt_out_token",
]
