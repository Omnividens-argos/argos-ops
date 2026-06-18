"""Tests du catalogue de canaux du pôle Marketing (archi v2, S2).

Verrouille ``Channel.length_ok`` (borne max/min + format long sans plafond) qui
pilote ``DraftOut.length_ok`` exposé au front (preview par canal).
"""

from __future__ import annotations

from argos_ops.poles.marketing.channels import (
    CHANNEL_IDS,
    get_channel,
    is_known_channel,
)


def test_lookup() -> None:
    assert is_known_channel("linkedin") is True
    assert is_known_channel("tiktok") is False
    assert get_channel("x") is not None
    assert get_channel("inconnu") is None
    assert set(CHANNEL_IDS) >= {"linkedin", "x", "blog", "newsletter"}


def test_length_ok_max_bound() -> None:
    x = get_channel("x")
    assert x is not None and x.max_chars == 280
    assert x.length_ok("a" * 280) is True
    assert x.length_ok("a" * 281) is False


def test_length_ok_min_bound() -> None:
    li = get_channel("linkedin")
    assert li is not None and li.min_chars == 1300
    assert li.length_ok("a" * 100) is False  # sous le minimum
    assert li.length_ok("a" * 1300) is True
    assert li.length_ok("a" * 2001) is False  # au-dessus du maximum


def test_length_ok_long_form_no_cap() -> None:
    blog = get_channel("blog")
    assert blog is not None and blog.max_chars == 0
    assert blog.length_ok("a" * 10000) is True  # pas de plafond dur
    assert blog.social is False
