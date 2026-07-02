"""
Scraper voor WBOS Makelaars (wbosmakelaars.nl).
Kaarten zijn <div class="house"> met daarin plaats, adres, prijs
en een statuslabel (Verhuurd / Te huur / ...).
"""

import os
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import log, HEADERS, parse_prijs

SITE_NAME = "wbos"
SITE_LABEL = "WBOS Makelaars"
URL = "https://wbosmakelaars.nl/woningaanbod/huur/"

# Kaarten met deze status slaan we over: die woning is al weg
SKIP_STATUS = ["verhuurd", "verkocht", "onder optie", "onder bod"]


def fetch_listings():
    log(f"[{SITE_NAME}] Pagina ophalen: {URL}")
    response = requests.get(URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    page_size = len(response.text)

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("div.house")

    listings = []
    for card in cards:
        status_el = card.select_one(".status")
        status = status_el.get_text(strip=True).lower() if status_el else ""
        if any(skip in status for skip in SKIP_STATUS):
            continue

        link = card.select_one("a.coverlink") or card.find("a", href=True)
        city_el = card.select_one("span.text-muted")
        title_el = card.find("h4")
        price_el = card.select_one("span.fw-bold")
        if not link or not title_el:
            continue

        city = city_el.get_text(strip=True) if city_el else ""
        title = title_el.get_text(strip=True)
        price_text = price_el.get_text(strip=True) if price_el else ""

        listings.append({
            "url": link["href"],
            "title": f"{title}, {city}" if city else title,
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
            "container_found": len(cards) > 0,
        },
    }
