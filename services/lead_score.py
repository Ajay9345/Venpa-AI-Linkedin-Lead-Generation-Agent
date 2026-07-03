from __future__ import annotations

import re
from typing import Optional

import pandas as pd

DESIGNATION_SCORE_RULES: list[tuple[str, int]] = sorted([
    ("founder", 100), ("owner", 98), ("ceo", 96), ("chief executive officer", 96),
    ("co-founder", 95), ("cofounder", 95), ("managing director", 92), ("director", 90),
    ("vice president", 85), ("vp", 85), ("manager", 80), ("sales manager", 78),
    ("business development", 76), ("executive", 70), ("intern", 40),
], key=lambda r: -len(r[0]))

DEFAULT_SCORE = 50


def calculate_lead_score(designation: Optional[str], headline: Optional[str] = None) -> int:
    def norm(t): return t.strip().lower() if t and isinstance(t, str) else ""
    text = f"{norm(designation)} {norm(headline)}".strip()
    if not text:
        return DEFAULT_SCORE
    for keyword, score in DESIGNATION_SCORE_RULES:
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            return score
    return DEFAULT_SCORE


def _company_score(followers) -> int:
    try:
        n = int(str(followers).replace(",", "").strip())
        if n >= 100000: return 90
        if n >= 10000: return 75
        if n >= 1000: return 60
        return 40
    except (ValueError, TypeError):
        return DEFAULT_SCORE


def apply_lead_scores(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        df["Lead Score"] = []
        return df
    df = df.copy()
    if "Company Name" in df.columns:
        df["Lead Score"] = df.get("Followers", pd.Series(["N/A"] * len(df))).apply(_company_score)
    else:
        desig = df.get("Designation", pd.Series([""] * len(df)))
        heads = df.get("Headline", pd.Series([""] * len(df)))
        df["Lead Score"] = [calculate_lead_score(d, h) for d, h in zip(desig, heads)]
    return df.sort_values("Lead Score", ascending=False).reset_index(drop=True)


def score_badge_color(score: int) -> str:
    if score >= 90: return "green"
    if score >= 70: return "orange"
    return "red"


def score_tier_label(score: int) -> str:
    if score >= 90: return "Hot Lead"
    if score >= 70: return "Warm Lead"
    return "Cold Lead"
