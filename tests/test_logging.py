"""Tests du filtre anti-fuite secrets sur les logs."""

from __future__ import annotations

from argos_ops.logging import _redact


def test_redact_discord_webhook_keeps_id_redacts_token() -> None:
    msg = "POST https://discord.com/api/webhooks/1501912468384120862/abcdef-XYZ_token-1234567890"
    out = _redact(msg)
    assert "1501912468384120862" in out  # ID public conservé pour corrélation
    assert "abcdef-XYZ_token-1234567890" not in out
    assert "[REDACTED]" in out


def test_redact_openai_anthropic_sk_key() -> None:
    msg = "Authorization: Bearer sk-abc123def456ghi789jkl012mno"
    out = _redact(msg)
    assert "sk-abc123def456ghi789jkl012mno" not in out
    assert "sk-[REDACTED]" in out


def test_redact_google_aiza_key() -> None:
    msg = "GEMINI_API_KEY=AIzaSyDfakefakefakefakefakefakefakefakefake"
    out = _redact(msg)
    assert "AIzaSyDfakefakefakefakefakefakefakefakefake" not in out
    assert "AIza[REDACTED]" in out


def test_redact_github_token() -> None:
    msg = "git push using ghp_AbCdEf1234567890AbCdEf1234567890AbCd"
    out = _redact(msg)
    assert "ghp_AbCdEf1234567890AbCdEf1234567890AbCd" not in out
    assert "gh_[REDACTED]" in out


def test_redact_slack_xoxb_token() -> None:
    msg = "Slack token: xoxb-1234567890-abcdefghijklmnopqrstuvwx"
    out = _redact(msg)
    assert "xoxb-1234567890-abcdefghijklmnopqrstuvwx" not in out
    assert "xox_[REDACTED]" in out


def test_redact_stripe_webhook_secret() -> None:
    msg = "STRIPE_WEBHOOK_SECRET=whsec_AbCdEfGhIjKlMnOpQrStUvWxYz1234"
    out = _redact(msg)
    assert "whsec_AbCdEfGhIjKlMnOpQrStUvWxYz1234" not in out
    assert "whsec_[REDACTED]" in out


def test_redact_aws_access_key() -> None:
    msg = "AccessKeyId: AKIAIOSFODNN7EXAMPLE"
    out = _redact(msg)
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "AKIA[REDACTED]" in out


def test_redact_jwt_access_token() -> None:
    # JWT 3 segments — couvre les access tokens AT Protocol Bluesky + Bearer.
    jwt = (
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJkaWQ6cGxjOmFiYyJ9."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    out = _redact(f"Authorization: Bearer {jwt}")
    assert jwt not in out
    assert "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" not in out
    assert "eyJ[REDACTED-JWT]" in out


def test_redact_bluesky_app_password() -> None:
    msg = "BLUESKY_APP_PASSWORD=abcd-efgh-ijkl-mnop posting toot"
    out = _redact(msg)
    assert "abcd-efgh-ijkl-mnop" not in out
    assert "[REDACTED-BSKY-APPPW]" in out


def test_redact_meta_graph_token() -> None:
    # Token avec '_' ET '-' (forme réelle Meta) : la queue ne doit PAS fuiter.
    token = "EAAGm0PX4ZCpsBOZBxyz1234567890ABCDqrst_uvwXYZ-abcdEFGH9876543210ZD"
    out = _redact(f"META_PAGE_ACCESS_TOKEN={token} posting feed")
    assert token not in out
    assert "_uvwXYZ-abcdEFGH9876543210ZD" not in out  # la queue après le 1er '_'
    assert "EAA[REDACTED-META]" in out


def test_redact_idempotent_non_secret_message() -> None:
    msg = "DigestBuilder OK — leads=12 customers=1 tickets_open=4"
    out = _redact(msg)
    assert out == msg


def test_redact_multiple_secrets_in_one_message() -> None:
    msg = (
        "Connecting with sk-myopenaikey1234567890abcdef "
        "and posting to https://discord.com/api/webhooks/999/secrettokenhere"
    )
    out = _redact(msg)
    assert "sk-myopenaikey1234567890abcdef" not in out
    assert "secrettokenhere" not in out
    assert "999" in out  # ID Discord public conservé
