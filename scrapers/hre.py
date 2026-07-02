"""
Scraper voor Haarlem Real Estate (haarlemrealestate.nl).
De woningen worden geladen via een JSON-feed:
GET /en/realtime-listings/consumer
Elke woning heeft o.a. isRentals, rentalsPrice, city, status en url.
"""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import log, HEADERS

SITE_NAME = "hre"
SITE_LABEL = "Haarlem Real Estate"
JSON_URL = "https://www.haarlemrealestate.nl/en/realtime-listings/consumer"
BASE = "https://www.haarlemrealestate.nl"

# Woningen met deze status slaan we over: die zijn al weg
SKIP_STATUS = ["rented", "sold", "option", "verhuurd", "verkocht"]


def fetch_listings():
    log(f"[{SITE_NAME}] JSON-feed ophalen: {JSON_URL}")
    response = requests.get(JSON_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    page_size = len(response.text)
    data = response.json()

    listings = []
    for item in data:
        if not item.get("isRentals"):
            continue  # koopwoning
        status = (item.get("status") or "").lower()
        if any(skip in status for skip in SKIP_STATUS):
            continue

        address = item.get("address") or "Onbekend"
        city = item.get("city") or ""
        prijs = item.get("rentalsPrice") or None
        price_text = item.get("price") or (
            f"€ {prijs:,}".replace(",", ".") + " p.m." if prijs else "")

        url = item.get("url") or ""
        if url.startswith("/"):
            url = BASE + url

        listings.append({
            "url": url,
            "title": f"{address}, {city}" if city else address,
            "city": city,
            "price_text": price_text,
            "price_eur": prijs,
        })

    log(f"[{SITE_NAME}] {len(listings)} beschikbare listings gevonden "
        f"({len(data)} in de feed)")
    return {
        "listings": listings,
        "health": {
            "page_size": page_size,
            # De feed is gezond als het geldige JSON-lijst was
            "container_found": isinstance(data, list),
        },
    }
