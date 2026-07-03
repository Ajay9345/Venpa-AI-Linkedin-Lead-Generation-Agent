from __future__ import annotations

import math
import os
from typing import Any

from apify_client import ApifyClient
from apify_client.errors import ApifyApiError

DEFAULT_ACTOR_ID = "harvestapi/linkedin-profile-search"
COMPANY_ACTOR_ID = "harvestapi/linkedin-company-search"


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


# Maps filter dict keys → (run_input key, is_list)
_LIST_FILTERS = {
    "location": "locations",
    "current_job_title": "currentJobTitles",
    "past_job_title": "pastJobTitles",
    "current_company": "currentCompanies",
    "past_company": "pastCompanies",
    "school": "schools",
    "industry": "industries",
    "keyword": "keywords",
    "first_name": "firstNames",
    "last_name": "lastNames",
    "company_hq_location": "companyHeadquarterLocations",
}
_SCALAR_FILTERS = {
    "years_of_experience": "yearsOfExperience",
    "years_at_current_company": "yearsAtCurrentCompany",
}
_WRAPPED_FILTERS = {
    "seniority": "seniorities",
    "function": "functions",
    "company_headcount": "companyHeadcounts",
    "profile_language": "profileLanguages",
}


def run_linkedin_search(
    query: str,
    max_results: int = 100,
    lead_type: str = "People",
    filters: dict | None = None,
) -> list[dict[str, Any]]:
    if not query or not query.strip():
        raise ApifyServiceError("Search query cannot be empty.")

    token = get_api_token()
    actor_id = get_actor_id(lead_type)
    client = ApifyClient(token)
    filters = filters or {}

    def _str(key): return (filters.get(key) or "").strip()

    if lead_type == "Company":
        run_input: dict[str, Any] = {
            "searchQuery": query,
            "maxItems": max_results,
            "takePages": max(1, math.ceil(max_results / 25)),
        }
        for fk, rk in [("location", "locations"), ("industry", "industries"), ("keyword", "keywords")]:
            if v := _str(fk):
                run_input[rk] = [v]
        if v := _str("company_headcount"):
            run_input["companyHeadcounts"] = [v]
    else:
        run_input = {
            "searchQuery": query,
            "maxItems": max_results,
            "takePages": max(1, math.ceil(max_results / 25)),
        }
        for fk, rk in _LIST_FILTERS.items():
            if v := _str(fk):
                run_input[rk] = [v]
        for fk, rk in _SCALAR_FILTERS.items():
            if v := _str(fk):
                run_input[rk] = v
        for fk, rk in _WRAPPED_FILTERS.items():
            if v := _str(fk):
                run_input[rk] = [v]

    try:
        run = client.actor(actor_id).call(run_input=run_input)
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
        items = list(client.dataset(dataset_id).iterate_items())
    except ApifyApiError as exc:
        raise _translate_api_error(exc) from exc

    if not items:
        raise NoLeadsFoundError("No leads were found for this search query. Try broadening your search.")

    return items


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
