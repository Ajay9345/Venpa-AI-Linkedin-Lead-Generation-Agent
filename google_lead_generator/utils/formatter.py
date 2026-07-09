import pandas as pd


def join_values(values):
    """Convert a list into comma-separated text."""

    if isinstance(values, list):
        return ", ".join(str(value) for value in values if value)

    return values or ""


def format_results(results):

    formatted_data = []

    for item in results:

        formatted_data.append({

            "Business Name": item.get("title", ""),
            "Category": item.get("categoryName", ""),
            "Rating": item.get("totalScore", ""),
            "Reviews": item.get("reviewsCount", ""),
            "Phone": item.get("phone", ""),
            "Email": join_values(item.get("emails", [])),
            "Website": item.get("website", ""),
            "Address": item.get("address", ""),
            "City": item.get("city", ""),
            "State": item.get("state", ""),
            #"Facebook": join_values(social.get("facebooks", [])),
            #"Instagram": join_values(social.get("instagrams", [])),
            #"Twitter": join_values(social.get("twitters", [])),
            #"YouTube": join_values(social.get("youtubes", [])),
            #"TikTok": join_values(social.get("tiktoks", [])),
            #"LinkedIn": join_values(social.get("linkedIns", [])),
            #"Pinterest": join_values(social.get("pinterests", [])),
            #"Discord": join_values(social.get("discords", [])),
            #"Latitude": item.get("location", {}).get("lat", ""),
            #"Longitude": item.get("location", {}).get("lng", ""),
            "Country": item.get("countryCode", ""),
            "Postal Code": item.get("postalCode", ""),
            "Opening Hours": ", ".join(
                f"{hour['day']}: {hour['hours']}"
                for hour in item.get("openingHours", [])
                if isinstance(hour, dict)
            ),
            "Google Maps URL": item.get("url", ""),
            "Scraped At": item.get("scrapedAt", "")

        })

    return pd.DataFrame(formatted_data)