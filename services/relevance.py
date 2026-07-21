from __future__ import annotations

import re
from difflib import SequenceMatcher

import pandas as pd

RELEVANCE_COL = "_relevance"
PRIMARY_RELEVANCE_COL = "_primary_relevance"
MIN_RELEVANCE = 20  # below this, a lead's industry/description doesn't actually match the search


def _norm(text) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    text = str(text).strip()
    return "" if text in ("", "N/A") else text.lower()


def _location_matches(lead_location: str, wanted: str) -> bool:
    parts = [p.strip() for p in re.split(r"[,|]", lead_location) if p.strip()]
    for part in parts:
        if wanted in part or part in wanted:
            return True
        if SequenceMatcher(None, wanted, part).ratio() >= 0.8:
            return True
    return False


def _text_score(haystacks: list[str], needle: str) -> int:
    """0 = no signal, 50 = neutral (needle blank), 100 = clear match, 20 = no match found."""
    if not needle:
        return 50
    for hay in haystacks:
        if not hay:
            continue
        if needle in hay:
            return 100
        if SequenceMatcher(None, needle, hay).ratio() >= 0.6:
            return 80
    return 20


def apply_location_filter(df: pd.DataFrame, location_filter: str) -> pd.DataFrame:
    """Lenient hard filter: drop only rows with a known location that clearly doesn't match.
    Rows with a blank/unknown location are kept — unknown isn't the same as mismatched."""
    wanted = _norm(location_filter)
    if not wanted or df.empty:
        return df

    def _keep(loc) -> bool:
        loc_norm = _norm(loc)
        if not loc_norm:
            return True
        return _location_matches(loc_norm, wanted)

    return df[df["Location"].apply(_keep)].reset_index(drop=True)


def filter_relevant(df: pd.DataFrame, min_score: int = MIN_RELEVANCE) -> pd.DataFrame:
    """Hard filter using the `_primary_relevance` column: drops leads whose authoritative
    field — LinkedIn's own Industry category for companies, Headline for people — doesn't
    actually match the search query. Deliberately ignores free-text Description/About, since
    an IT consultancy's "we serve real estate, healthcare, retail clients" blurb would
    otherwise let it pass a "real estate" search. Requires score_relevance() to have run first."""
    if df.empty or PRIMARY_RELEVANCE_COL not in df.columns:
        return df
    return df[df[PRIMARY_RELEVANCE_COL] >= min_score].reset_index(drop=True)


def score_relevance(df: pd.DataFrame, query: str, filters: dict) -> pd.DataFrame:
    """Adds `_primary_relevance` (authoritative-field match, used by filter_relevant) and
    `_relevance` (blended with secondary fields, used only to rank the remaining matches so
    the strongest survive when there's a surplus over max_results)."""
    if df.empty:
        df[RELEVANCE_COL] = pd.Series(dtype=int)
        df[PRIMARY_RELEVANCE_COL] = pd.Series(dtype=int)
        return df

    df = df.copy()
    is_company = "Company Name" in df.columns
    filters = filters or {}

    query_n = _norm(query)
    industry_n = _norm(filters.get("industry"))
    keyword_n = _norm(filters.get("keyword"))
    seniority_n = _norm(filters.get("seniority"))
    function_n = _norm(filters.get("function"))
    headcount_n = _norm(filters.get("company_headcount"))
    needle = industry_n or query_n

    scores = []
    primary_scores = []
    for _, row in df.iterrows():
        components = []

        if is_company:
            primary_fields = [_norm(row.get("Industry"))]
            secondary_fields = [_norm(row.get("Description"))]
            primary_score = _text_score(primary_fields, needle)
            components.append(primary_score)
            components.append(_text_score(secondary_fields, needle) if needle else 50)
            components.append(_text_score(primary_fields + secondary_fields, keyword_n))
            if headcount_n:
                components.append(_text_score([_norm(row.get("Company Size"))], headcount_n))
        else:
            primary_fields = [_norm(row.get("Headline")), _norm(row.get("Company"))]
            secondary_fields = [_norm(row.get("About"))]
            primary_score = _text_score(primary_fields, needle)
            components.append(primary_score)
            components.append(_text_score(secondary_fields, needle) if needle else 50)
            components.append(_text_score(primary_fields + secondary_fields, keyword_n))
            title_fields = [_norm(row.get("Designation")), _norm(row.get("Headline"))]
            if seniority_n:
                components.append(_text_score(title_fields, seniority_n))
            if function_n:
                components.append(_text_score(title_fields, function_n))

        components = [c for c in components if c is not None]
        scores.append(round(sum(components) / len(components)) if components else 50)
        primary_scores.append(primary_score)

    df[RELEVANCE_COL] = scores
    df[PRIMARY_RELEVANCE_COL] = primary_scores
    return df
