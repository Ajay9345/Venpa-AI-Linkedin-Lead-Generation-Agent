import os
from dotenv import load_dotenv

load_dotenv()


APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ACTOR_ID = os.getenv("ACTOR_ID")


START_RUN_URL = (
    f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"
)

RUN_STATUS_URL = (
    "https://api.apify.com/v2/actor-runs/{run_id}"
)

DATASET_ITEMS_URL = (
    "https://api.apify.com/v2/datasets/{dataset_id}/items"
)


DEFAULT_PAYLOAD = {
    "searchStringsArray": [],
    "locationQuery": "",
    "maxCrawledPlacesPerSearch": 20,
    "language": "en",
    "searchMatching": "all",
    "placeMinimumStars": "",
    "website": "allPlaces",
    "skipClosedPlaces": False,
    "scrapePlaceDetailPage": True,
    "scrapeTableReservationProvider": False,
    "scrapeOrderOnline": False,
    "includeWebResults": False,
    "scrapeDirectories": False,
    "maxQuestions": 0,
    "scrapeContacts": True,
    "scrapeSocialMediaProfiles": {
        "facebooks": False,
        "instagrams": False,
        "youtubes": False,
        "tiktoks": False,
        "twitters": False,
    },
    "maximumLeadsEnrichmentRecords": 0,
    "verifyLeadsEnrichmentEmails": False,
    "maxReviews": 0,
    "reviewsSort": "newest",
    "reviewsFilterString": "",
    "reviewsOrigin": "all",
    "scrapeReviewsPersonalData": False,
    "maxImages": 0,
    "scrapeImageAuthors": False,
    "enableCompetitorAnalysis": False,
    "maxCompetitorsToAnalyze": 30,
    "allPlacesNoSearchAction": "",
}