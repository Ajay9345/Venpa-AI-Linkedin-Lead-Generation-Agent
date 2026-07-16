from __future__ import annotations

import math
import os
import time
from typing import Any

from apify_client import ApifyClient
from apify_client.errors import ApifyApiError

DEFAULT_ACTOR_ID = "harvestapi/linkedin-profile-search"
COMPANY_ACTOR_ID = "harvestapi/linkedin-company-search"

PAGE_SIZE = 25
OVERFETCH_MULTIPLIER = 3
MAX_PAGES = 12  # 12 * PAGE_SIZE = 300 items, a generous ceiling on cost/time per search


class ApifyServiceError(Exception): pass
class MissingTokenError(ApifyServiceError): pass
class InvalidTokenError(ApifyServiceError): pass
class ActorNotFoundError(ApifyServiceError): pass
class RateLimitError(ApifyServiceError): pass
class ActorRunFailedError(ApifyServiceError): pass
class NoLeadsFoundError(ApifyServiceError): pass
class ApifyTimeoutError(ApifyServiceError): pass


def get_api_token() -> str:
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        raise MissingTokenError("No Apify API token found. Please set APIFY_TOKEN in your .env file.")
    return token


def get_actor_id(lead_type: str = "People") -> str:
    if lead_type == "Company":
        return os.getenv("APIFY_COMPANY_ACTOR_ID", COMPANY_ACTOR_ID).strip() or COMPANY_ACTOR_ID
    return os.getenv("APIFY_ACTOR_ID", DEFAULT_ACTOR_ID).strip() or DEFAULT_ACTOR_ID


def initial_take_pages(max_results: int) -> int:
    """Pages to request on the first attempt: enough headroom for downstream ranking/trimming
    losses (dedup, location mismatch) without over-requesting on every search."""
    wanted_pages = math.ceil(max_results / PAGE_SIZE) * OVERFETCH_MULTIPLIER
    return min(max(wanted_pages, 1), MAX_PAGES)


# Maps filter dict keys → run_input key. Only free-text list params verified against the
# harvestapi actor schema are sent here. Enum-coded filters (industry, seniority, function,
# years of experience/at company, company headcount, profile language) aren't reliably
# expressible as free text against the actor's real (ID-based) schema, so they're applied as
# post-fetch relevance signals instead (see services/relevance.py) rather than sent here.
_LIST_FILTERS = {
    "location": "locations",
    "current_job_title": "currentJobTitles",
    "past_job_title": "pastJobTitles",
    "current_company": "currentCompanies",
    "past_company": "pastCompanies",
    "school": "schools",
    "keyword": "keywords",
    "first_name": "firstNames",
    "last_name": "lastNames",
    "company_hq_location": "companyHeadquarterLocations",
}


def run_linkedin_search(
    query: str,
    lead_type: str = "People",
    filters: dict | None = None,
    take_pages: int = 3,
    start_page: int = 1,
) -> list[dict[str, Any]]:
    """Fetches one page-range from Apify. Callers doing a multi-attempt backfill should advance
    `start_page` by the number of pages already fetched, rather than re-requesting from page 1 —
    the actor bills per page scraped, so re-fetching page 1 on every attempt would double-bill."""
    if not query or not query.strip():
        raise ApifyServiceError("Search query cannot be empty.")

    token = get_api_token()
    actor_id = get_actor_id(lead_type)
    client = ApifyClient(token)
    filters = filters or {}

    def _str(key): return (filters.get(key) or "").strip()

    run_input: dict[str, Any] = {
        "searchQuery": query,
        "startPage": start_page,
        "takePages": take_pages,
        "maxItems": take_pages * PAGE_SIZE,
    }
    if lead_type == "Company":
        for fk, rk in [("location", "locations"), ("keyword", "keywords")]:
            if v := _str(fk):
                run_input[rk] = [v]
    else:
        for fk, rk in _LIST_FILTERS.items():
            if v := _str(fk):
                run_input[rk] = [v]

    try:
        run = _call_actor_with_retry(client, actor_id, run_input)
    except ApifyApiError as exc:
        raise _translate_api_error(exc) from exc
    except Exception as exc:
        msg = str(exc).lower()
        if "timeout" in msg or "timed out" in msg:
            raise ApifyTimeoutError("The Apify API request timed out. Please try again.") from exc
        if "connection" in msg or "network" in msg:
            raise ApifyServiceError("No internet connection or the Apify API is unreachable.") from exc
        raise ApifyServiceError(f"Unexpected error while running the actor: {exc}") from exc

    if run is None:
        raise ApifyTimeoutError("The actor run did not complete.")

    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id:
        raise ActorRunFailedError("The actor run did not return a valid dataset.")

    if (getattr(run, "status", "") or "").upper() != "SUCCEEDED":
        raise ActorRunFailedError(f"Actor run finished with status: {getattr(run, 'status', 'UNKNOWN')}")

    try:
        return list(client.dataset(dataset_id).iterate_items())
    except ApifyApiError as exc:
        raise _translate_api_error(exc) from exc


def _call_actor_with_retry(client: ApifyClient, actor_id: str, run_input: dict[str, Any], retries: int = 1):
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return client.actor(actor_id).call(run_input=run_input)
        except ApifyApiError as exc:
            translated = _translate_api_error(exc)
            if attempt < retries and isinstance(translated, (RateLimitError, ApifyTimeoutError)):
                last_exc = exc
                time.sleep(2)
                continue
            raise
    raise last_exc  # pragma: no cover - unreachable, satisfies type checkers


def _translate_api_error(exc: ApifyApiError) -> ApifyServiceError:
    code = getattr(exc, "status_code", None)
    msg = str(exc).lower()
    if code == 401 or "unauthorized" in msg or "invalid token" in msg:
        return InvalidTokenError("The Apify API token is invalid or has expired.")
    if code == 404 or "not found" in msg:
        return ActorNotFoundError("The configured Apify actor could not be found.")
    if code == 429 or "rate limit" in msg or "too many requests" in msg:
        return RateLimitError("Apify API rate limit reached. Please wait and try again.")
    if "dataset" in msg and ("unavailable" in msg or "empty" in msg):
        return NoLeadsFoundError("The dataset for this run is unavailable or empty.")
    return ApifyServiceError(f"Apify API error: {exc}")
