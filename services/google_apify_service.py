import copy
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ACTOR_ID = os.getenv("GOOGLE_ACTOR_ID", "compass~crawler-google-places")

START_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"
RUN_STATUS_URL = "https://api.apify.com/v2/actor-runs/{run_id}"
DATASET_ITEMS_URL = "https://api.apify.com/v2/datasets/{dataset_id}/items"

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
    "scrapeContacts": True,
    "maxReviews": 0,
    "maxImages": 0,
}


class GoogleApifyService:

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {APIFY_TOKEN}",
            "Content-Type": "application/json",
        }

    def build_payload(self, query, location, max_results):
        payload = copy.deepcopy(DEFAULT_PAYLOAD)
        payload["searchStringsArray"] = [query]
        payload["locationQuery"] = location
        payload["maxCrawledPlacesPerSearch"] = max_results
        return payload

    def start_actor(self, query, location, max_results):
        response = requests.post(
            START_RUN_URL,
            headers=self.headers,
            json=self.build_payload(query, location, max_results),
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["data"]

    def wait_for_finish(self, run_id):
        while True:
            response = requests.get(
                RUN_STATUS_URL.format(run_id=run_id),
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            run = response.json()["data"]
            status = run["status"]
            if status == "SUCCEEDED":
                return run
            if status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                raise Exception(f"Actor finished with status: {status}")
            time.sleep(5)

    def get_dataset(self, dataset_id):
        response = requests.get(
            DATASET_ITEMS_URL.format(dataset_id=dataset_id),
            headers=self.headers,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    def run(self, query, location, max_results):
        run = self.start_actor(query, location, max_results)
        completed_run = self.wait_for_finish(run["id"])
        return self.get_dataset(completed_run["defaultDatasetId"])
