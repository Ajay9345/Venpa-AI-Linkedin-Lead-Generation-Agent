from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

DECISION_MAKER_KEYWORDS = [
    "founder", "owner", "ceo", "co-founder", "cofounder",
    "managing director", "director", "vice president", "vp",
]


def compute_metrics(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"total_leads": 0, "companies_found": 0, "cities": 0, "decision_makers": 0,
                "avg_score": 0, "highest_score": 0, "lowest_score": 0}

    scores = df.get("Lead Score", pd.Series([0]))
    is_company = "Company Name" in df.columns

    if is_company:
        decision_makers = 0
        companies_found = df["Company Name"].replace("N/A", pd.NA).nunique()
    else:
        text = (df.get("Designation", pd.Series(dtype=str)).astype(str).str.lower()
                + " " + df.get("Headline", pd.Series(dtype=str)).astype(str).str.lower())
        decision_makers = int(text.apply(lambda x: any(k in x for k in DECISION_MAKER_KEYWORDS)).sum())
        companies_found = df["Company"].replace("N/A", pd.NA).nunique()

    return {
        "total_leads": len(df),
        "companies_found": companies_found,
        "cities": df["Location"].replace("N/A", pd.NA).nunique(),
        "decision_makers": decision_makers,
        "avg_score": round(scores.mean(), 1),
        "highest_score": int(scores.max()),
        "lowest_score": int(scores.min()),
    }


def _plot(series: pd.Series, title: str, horizontal=False):
    fig, ax = plt.subplots(figsize=(8, 4))
    if series.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
    elif horizontal:
        series.plot.barh(ax=ax)
    else:
        series.plot.bar(ax=ax)
        plt.xticks(rotation=45, ha="right")
    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel("Count")
    plt.tight_layout()
    return fig


def chart_leads_by_city(df):
    return _plot(df[df["Location"] != "N/A"]["Location"].value_counts().head(10), "Leads by City")


def chart_top_companies(df):
    return _plot(
        df[df["Company"] != "N/A"]["Company"].value_counts().head(10).sort_values(),
        "Top Companies", horizontal=True,
    )


def chart_designation_distribution(df):
    return _plot(df[df["Designation"] != "N/A"]["Designation"].value_counts().head(10), "Designation Distribution")


def chart_lead_score_distribution(df):
    fig, ax = plt.subplots(figsize=(8, 4))
    if not df.empty:
        ax.hist(df["Lead Score"], bins=20)
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
    ax.set_title("Lead Score Distribution")
    ax.set_xlabel("Lead Score")
    ax.set_ylabel("Count")
    plt.tight_layout()
    return fig


def chart_top_scoring_leads(df):
    name_col = "Company Name" if "Company Name" in df.columns else "Full Name"
    top = df.nlargest(10, "Lead Score").sort_values("Lead Score").set_index(name_col)["Lead Score"]
    label = "Companies" if name_col == "Company Name" else "Leads"
    return _plot(top, f"Top 10 Highest Scoring {label}", horizontal=True)
