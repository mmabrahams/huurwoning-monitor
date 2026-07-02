"""
Scraper voor Rotsvast (rotsvast.nl).
Let op: de oude URL /woningaanbod/?type=2 bestaat niet meer.
We gebruiken de zoekpagina /huren/ met een serverside filter:
zoeken op Haarlem met een straal van 10 km (dekt ook Heemstede,
Santpoort en Overveen). Kaarten zijn <a class="card card--house">.
"""

import os
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import log, HEADERS, parse_prijs

SITE_NAME = "rotsvast"
SITE_LABEL = "Rotsvast"
URL = "https://www.rotsvast.nl/huren/?search=Haarlem&radius=10"

# Kaarten met deze labels slaan we over: die woning is al weg
SKIP_LABELS = ["verhuurd", "onder optie", "verkocht"]


def fetch_listings():
    log(f"[{SITE_NAME}] Pagina ophalen: {URL}")
    response = requests.get(URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    page_size = len(response.text)

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("a.card--house")

    listings = []
    for card in cards:
        label_el = card.select_one(".card-house__label")
        label = label_el.get_text(strip=True).lower() if label_el else ""
        if any(skip in label for skip in SKIP_LABELS):
            continue

        title_el = card.select_one(".card-house__title")
        texts = card.select(".card-house__text")
        city = texts[0].get_text(strip=True) if texts else ""
        price_text = ""
        for t in texts:
            if "€" in t.get_text():
                price_text = t.get_text(strip=True)

        title = title_el.get_text(strip=True) if title_el else "Onbekend"
        listings.append({
            "url": card["href"],
            "title": f"{title}, {city}" if city else title,
            "city": city,
            "price_text": price_text,
            "price_eur": parse_prijs(price_text),
        })

    log(f"[{SITE_NAME}] {len(listings)} listings gevonden")
    return {
        "listings": listings,
        "health": {
            "page_size": page_size,
            # De zoekpagina kan legitiem 0 resultaten hebben; check daarom
            # op de aanwezigheid van de resultatencontainer in de HTML
            "container_found": "house-list" in response.text,
        },
    }
