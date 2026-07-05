from __future__ import annotations

import json
import os
import re

import pandas as pd


def _groq_client():
    from groq import Groq
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return None
    return Groq(api_key=key)


def _unique_values(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    is_company = "Company Name" in df.columns
    locations = sorted({v for v in df["Location"].dropna().unique() if v and v != "N/A"})
    industry_col = "Industry" if is_company else "Company"
    industries = sorted({v for v in df[industry_col].dropna().unique() if v and v != "N/A"})
    return locations, industries


def apply_groq_filter(df: pd.DataFrame, search_query: str, location_filter: str) -> pd.DataFrame:
    """Apply deterministic location filter, then use Groq only for industry filtering."""
    if df.empty:
        return df

    is_company = "Company Name" in df.columns
    industry_col = "Industry" if is_company else "Company"

    # --- Fuzzy location filter ---
    if location_filter and location_filter.strip():
        from difflib import SequenceMatcher
        city_input = location_filter.strip().lower()

        def _location_matches(loc: str) -> bool:
            parts = [p.strip() for p in re.split(r"[,|]", loc.lower())]
            for part in parts:
                if city_input in part or part in city_input:
                    return True
                if SequenceMatcher(None, city_input, part).ratio() >= 0.8:
                    return True
            return False

        matched = {loc for loc in df["Location"].dropna().unique() if _location_matches(loc)}
        df = df[df["Location"].isin(matched)].reset_index(drop=True)
        if df.empty:
            return df

    # --- Groq for industry filtering only ---
    client = _groq_client()
    if client is None:
        return df

    _, industries = _unique_values(df)

    prompt = f"""You are a lead filtering assistant.

User search query: "{search_query}"

From the list below, return ONLY the industries relevant to the search query. Remove unrelated ones.

Industries:
{json.dumps(industries, ensure_ascii=False)}

Respond ONLY with valid JSON: {{"industries": [...]}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1024,
        )
        content = response.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return pd.DataFrame(columns=df.columns)
        result = json.loads(match.group())
        approved_industries = {v.lower() for v in (result.get("industries") or [])}
        if approved_industries:
            df = df[df[industry_col].str.lower().isin(approved_industries)].reset_index(drop=True)
        return df
    except json.JSONDecodeError:
        return pd.DataFrame(columns=df.columns)
    except Exception:
        return df
