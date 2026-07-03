from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import pandas as pd

EXPECTED_COLUMNS: list[str] = [
    "Profile Image", "Full Name", "Headline", "Designation", "Company",
    "Location", "Company Size", "Followers", "Connections", "Experience",
    "About", "LinkedIn URL", "Company URL", "Search Query", "Lead Score",
]

COMPANY_COLUMNS: list[str] = [
    "Company Name", "Industry", "Location", "Company Size", "Followers",
    "Website", "LinkedIn URL", "Description", "Search Query", "Lead Score",
]


def is_valid_url(url) -> bool:
    if not url or not isinstance(url, str):
        return False
    try:
        p = urlparse(url.strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except ValueError:
        return False


def safe_url(url) -> str:
    return url.strip() if is_valid_url(url) else "N/A"


def clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    text = re.sub(r"\s+", " ", str(value).strip())
    return text if text else "N/A"


def normalize_company_record(raw: dict) -> dict:
    def pick(*keys):
        for k in keys:
            if raw.get(k) not in (None, ""):
                return raw[k]
        return None

    def _extract_industry(val):
        if not val:
            return None
        if isinstance(val, dict):
            return val.get("name") or val.get("title")
        if isinstance(val, list):
            parts = [
                (item.get("name") or item.get("title") or "") if isinstance(item, dict) else str(item)
                for item in val if item
            ]
            return ", ".join(p for p in parts if p) or None
        return str(val)

    def _extract_location(raw_):
        locs = raw_.get("locations")
        if isinstance(locs, list) and locs:
            entry = next((l for l in locs if isinstance(l, dict) and l.get("headquarter")), locs[0])
            if isinstance(entry, dict):
                parsed = entry.get("parsed") or {}
                if parsed.get("text"):
                    return parsed["text"]
                parts = [p for p in [entry.get("city"), entry.get("geographicArea"), entry.get("country")] if p]
                if parts:
                    return ", ".join(parts)
        for key in ("headquarter", "location"):
            loc = raw_.get(key)
            if not loc:
                continue
            if isinstance(loc, dict):
                parts = [p for p in [loc.get("city"), loc.get("geographicArea"), loc.get("country")] if p]
                return ", ".join(parts) if parts else (loc.get("linkedinText") or loc.get("text") or "")
            if isinstance(loc, str) and loc.strip():
                return loc.strip()
        return ""

    size = pick("staffCountRange", "companySize", "employeeCount", "staffCount")
    if isinstance(size, dict):
        size = f"{size.get('start', '')}–{size.get('end', '')}".strip("–")

    return {
        "Company Name": clean_text(pick("name", "companyName", "title")),
        "Industry": clean_text(_extract_industry(pick("industry", "industries"))),
        "Location": clean_text(_extract_location(raw)),
        "Company Size": clean_text(size),
        "Followers": clean_text(pick("followerCount", "followers")),
        "Website": safe_url(pick("websiteUrl", "website", "companyWebsite")),
        "LinkedIn URL": safe_url(pick("linkedinUrl", "url", "profileUrl")),
        "Description": clean_text(pick("description", "about", "summary")),
        "Search Query": clean_text(pick("searchQuery", "query")),
    }


def normalize_record(raw: dict) -> dict:
    def pick(*keys):
        for k in keys:
            if raw.get(k) not in (None, ""):
                return raw[k]
        return None

    first = raw.get("firstName") or ""
    last = raw.get("lastName") or ""
    full_name = f"{first} {last}".strip() or pick("fullName", "name", "full_name")

    pos = raw.get("currentPosition") or []
    if isinstance(pos, list):
        pos = pos[0] if pos and isinstance(pos[0], dict) else {}
    elif not isinstance(pos, dict):
        pos = {}

    headline = pick("headline", "title", "occupation")
    designation = pos.get("title") or pick("jobTitle", "designation")
    company = pos.get("companyName") or pick("companyName", "company")
    company_url = pos.get("companyUrl") or pick("companyUrl", "companyWebsite")
    company_size = pos.get("companyStaffCountRange") or pick("companySize", "employeeCount")

    loc = raw.get("location") or {}
    if isinstance(loc, dict):
        location = (loc.get("linkedinText") or loc.get("text") or loc.get("name")
                    or loc.get("parsed", {}).get("text")
                    or ", ".join(p for p in [loc.get("city"), loc.get("geographicArea"), loc.get("country")] if p)
                    or None)
    else:
        location = str(loc) if loc else None

    img = pick("profilePicture", "photo", "profileImage", "imageUrl", "avatar")
    if isinstance(img, dict):
        img = img.get("url") or img.get("src")

    exp = raw.get("experience")
    if isinstance(exp, list) and exp:
        e = exp[0] if isinstance(exp[0], dict) else {}
        exp = " at ".join(p for p in [e.get("position", ""), e.get("companyName", "")] if p) or None

    return {
        "Profile Image": img or "",
        "Full Name": clean_text(full_name),
        "Headline": clean_text(headline),
        "Designation": clean_text(designation or headline),
        "Company": clean_text(company),
        "Location": clean_text(location),
        "Company Size": clean_text(company_size),
        "Followers": clean_text(pick("followerCount", "followers")),
        "Connections": clean_text(pick("connectionsCount", "connections", "connectionCount")),
        "Experience": clean_text(exp or pick("about_experience", "yearsExperience")),
        "About": clean_text(pick("about", "summary", "bio")),
        "LinkedIn URL": safe_url(pick("linkedinUrl", "profileUrl", "url", "link")),
        "Company URL": safe_url(company_url),
        "Search Query": clean_text(pick("searchQuery", "query")),
    }


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df = df[df["Full Name"].notna() & (df["Full Name"] != "N/A")]
    df = df.drop_duplicates(subset=["LinkedIn URL"], keep="first")
    df = df.drop_duplicates(subset=["Full Name"], keep="first")
    display_cols = [c for c in EXPECTED_COLUMNS if c in df.columns and c != "Lead Score"]
    df = df.dropna(how="all", subset=display_cols)
    df["Full Name"] = df["Full Name"].astype(str).str.strip()
    return df.sort_values("Full Name").reset_index(drop=True)
