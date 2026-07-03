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
    """Send only unique locations + industries to Groq, then filter df locally."""
    if df.empty:
        return df

    client = _groq_client()
    if client is None:
        return df

    is_company = "Company Name" in df.columns
    industry_col = "Industry" if is_company else "Company"

    locations, industries = _unique_values(df)
    location_hint = f" Location filter: {location_filter.strip()}." if location_filter and location_filter.strip() else ""

    prompt = f"""You are a lead filtering assistant.
User search query: "{search_query}"{location_hint}

From the lists below, return ONLY the values that are relevant:
1. Keep locations that match or are within the requested location (city/region/country). If no location filter, keep all.
2. Keep industries/companies that are relevant to the search query. Remove clearly unrelated ones.

Locations: {json.dumps(locations, ensure_ascii=False)}
Industries: {json.dumps(industries, ensure_ascii=False)}

Respond ONLY with a raw JSON object, no explanation, no markdown:
{{"locations": [...], "industries": [...]}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=512,
        )
        content = response.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return df
        result = json.loads(match.group())
        approved_locations = set(result.get("locations") or [])
        approved_industries = set(result.get("industries") or [])

        mask = pd.Series([True] * len(df), index=df.index)
        if approved_locations:
            mask &= df["Location"].isin(approved_locations)
        if approved_industries:
            mask &= df[industry_col].isin(approved_industries)

        filtered = df[mask].reset_index(drop=True)
        return filtered if not filtered.empty else df
    except Exception:
        return df
