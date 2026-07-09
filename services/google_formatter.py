import pandas as pd


def format_google_results(results):
    formatted_data = []
    for item in results:
        formatted_data.append({
            "Business Name": item.get("title", ""),
            "Category": item.get("categoryName", ""),
            "Rating": item.get("totalScore", ""),
            "Reviews": item.get("reviewsCount", ""),
            "Phone": item.get("phone", ""),
            "Email": ", ".join(str(e) for e in item.get("emails", []) if e),
            "Website": item.get("website", ""),
            "Address": item.get("address", ""),
            "City": item.get("city", ""),
            "State": item.get("state", ""),
            "Country": item.get("countryCode", ""),
            "Postal Code": item.get("postalCode", ""),
            "Google Maps URL": item.get("url", ""),
        })
    return pd.DataFrame(formatted_data)
