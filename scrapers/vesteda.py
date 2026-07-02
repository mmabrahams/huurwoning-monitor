"""
Scraper voor Vesteda (vesteda.com).
De woningen staan NIET in de HTML (die worden met JavaScript geladen),
maar Vesteda heeft een JSON-API. We halen eerst de pagina op om de
actuele rootId en plaats-id te vinden, en roepen daarmee de API aan:
POST /api/units/search met {"s": <plaats-id>, "placeType": ..., "rootId": ...}
"""

import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import log, HEADERS

SITE_NAME = "vesteda"
SITE_LABEL = "Vesteda"
PAGE_URL = "https://www.vesteda.com/nl/huurwoningen-haarlem"
API_URL = "https://www.vesteda.com/api/units/search"
BASE = "https://www.vesteda.com"

# Reservewaarden voor als de pagina-structuur wijzigt (stand: juli 2026)
FALLBACK_ROOT_ID = 1303
FALLBACK_PLACE = "37"
FALLBACK_PLACE_TYPE = "5"


def fetch_listings():
    # Stap 1: haal de pagina op voor de actuele API-parameters
    log(f"[{SITE_NAME}] Pagina ophalen: {PAGE_URL}")
    response = requests.get(PAGE_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    html = response.text
    page_size = len(html)

    root_match = re.search(r"rootId\s*=\s*(\d+)", html)
    place_match = re.search(r"data-search-place=[\"']?(\d+)", html)
    type_match = re.search(r"data-search-place-type=[\"']?(\d+)", html)

    root_id = int(root_match.group(1)) if root_match else FALLBACK_ROOT_ID
    place = place_match.group(1) if place_match else FALLBACK_PLACE
    place_type = type_match.group(1) if type_match else FALLBACK_PLACE_TYPE
    container_found = bool(root_match and place_match)

    # Stap 2: roep de JSON-API aan
    log(f"[{SITE_NAME}] API aanroepen (plaats {place}, rootId {root_id})")
    api_response = requests.post(
        API_URL,
        json={"s": place, "placeType": place_type, "rootId": root_id},
        headers=HEADERS,
        timeout=15,
    )
    api_response.raise_for_status()
    data = api_response.json()

    listings = []
    for item in data.get("items", []):
        street = item.get("street") or ""
        number = item.get("houseNumber") or ""
        addition = item.get("houseNumberAddition") or ""
        title = " ".join(part for part in [street, str(number) + addition] if part).strip()
        city = item.get("city") or ""

        # Losse woningen hebben priceUnformatted; complexen een prijsrange
        prijs = item.get("priceUnformatted") or 0
        if prijs > 0:
            price_text = f"€ {prijs:,}".replace(",", ".") + " p.m."
            price_eur = prijs
        elif item.get("complexPriceMin"):
            price_eur = item["complexPriceMin"]
            pmax = item.get("complexPriceMax") or price_eur
            price_text = (f"€ {price_eur:,} - € {pmax:,} p.m. (complex)"
                          .replace(",", "."))
        else:
            price_text = ""
            price_eur = None

        url = item.get("url") or ""
        if url.startswith("/"):
            url = BASE + url

        listings.append({
            "url": url,
            "title": f"{title}, {city}" if city else title,
            "city": city,
            "price_text": price_text,
            "price_eur": price_eur,
        })

    log(f"[{SITE_NAME}] {len(listings)} listings gevonden")
    return {
        "listings": listings,
        "health": {
            "page_size": page_size,
            "container_found": container_found,
        },
    }
