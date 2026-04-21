from __future__ import annotations

from app.config import DigestConfig


def test_default_ratio_caps():
    cfg = DigestConfig(total_articles=15, ai_ratio=0.70)
    assert cfg.ai_cap == 10  # round(15 * 0.70) = 10
    assert cfg.general_cap == 5


def test_custom_ratio():
    cfg = DigestConfig(total_articles=20, ai_ratio=0.80)
    assert cfg.ai_cap == 16
    assert cfg.general_cap == 4


def test_caps_sum_to_total():
    for total in range(5, 30):
        for pct in (0.5, 0.6, 0.7, 0.8):
            cfg = DigestConfig(total_articles=total, ai_ratio=pct)
            assert cfg.ai_cap + cfg.general_cap == total
