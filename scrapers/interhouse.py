"""
Scraper voor Interhouse (interhouse.nl), vestiging Haarlem.
De woningen worden met JavaScript geladen, maar Interhouse heeft een
WordPress-AJAX-endpoint dat de woningkaarten als HTML teruggeeft:
POST /wp-admin/admin-ajax.php met action=building_results_action.
De vestiging Haarlem toont ook Heemstede, Hoofddorp enz. -
het plaatsfilter van de monitor doet de rest.
"""

import os
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import log, HEADERS, parse_prijs

SITE_NAME = "interhouse"
SITE_LABEL = "Interhouse"
AJAX_URL = "https://interhouse.nl/wp-admin/admin-ajax.php"
QUERY = ("?offer=huur&location_id=haarlem&sort=date-desc"
         "&number_of_results=50&language=nl_NL")

# Woningen met deze status slaan we over: die zijn al weg
SKIP_STATUS = ["verhuurd", "onder optie", "verkocht"]


def fetch_listings():
    log(f"[{SITE_NAME}] AJAX-endpoint aanroepen (vestiging Haarlem)")
    response = requests.post(
        AJAX_URL,
        data={"action": "building_results_action", "query": QUERY},
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    page_size = len(response.text)

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("a.building-result")

    listings = []
    for card in cards:
        status_el = card.select_one(".building-status")
        status = status_el.get_text(strip=True).lower() if status_el else ""
        if any(skip in status for skip in SKIP_STATUS):
            continue

        address_el = card.select_one(".c-result-item__title-address")
        city_el = card.select_one(".c-result-item__location-label")
        price_el = card.select_one(".c-result-item__price-label")

        address = address_el.get_text(strip=True) if address_el else "Onbekend"
        city = city_el.get_text(strip=True) if city_el else ""
        price_text = price_el.get_text(" ", strip=True) if price_el else ""

        listings.append({
            "url": card["href"],
            "title": f"{address}, {city}" if city else address,
            "city": city,
            "price_text": price_text,
            "price_eur": parse_prijs(price_text),
        })

    log(f"[{SITE_NAME}] {len(listings)} beschikbare listings gevonden "
        f"({len(cards)} kaarten totaal)")
    return {
        "listings": listings,
        "health": {
            "page_size": page_size,
            "container_found": "c-result-item" in response.text
                               or "building-result" in response.text,
        },
    }
