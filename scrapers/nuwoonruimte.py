"""
Scraper voor nuWoonruimte (nuwoonruimte.nl), huuraanbod.
Kaarten zijn <article class="object"> met een titel als
"Te huur: Zeestraat 67, 2042LB Zandvoort" en prijs in <span class="obj_price">.
"""

import os
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import log, HEADERS, parse_prijs

SITE_NAME = "nuwoonruimte"
SITE_LABEL = "nuWoonruimte"
URL = "https://www.nuwoonruimte.nl/woningaanbod/huur"
BASE = "https://www.nuwoonruimte.nl"

# Woningen met deze status slaan we over: die zijn al weg
SKIP_STATUS = ["verhuurd", "onder optie", "onder voorbehoud"]


def fetch_listings():
    log(f"[{SITE_NAME}] Pagina ophalen: {URL}")
    response = requests.get(URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    page_size = len(response.text)

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("article.object")

    listings = []
    for card in cards:
        status_el = card.select_one(".object_status")
        status = status_el.get_text(strip=True).lower() if status_el else ""
        if any(skip in status for skip in SKIP_STATUS):
            continue

        link = card.select_one("a.sys-property-link[href]")
        title_el = card.select_one(".object_address h2")
        price_el = card.select_one(".obj_price")
        if not link or not title_el:
            continue

        # Titel is bijv. "Te huur: Zeestraat 67, 2042LB Zandvoort"
        title = title_el.get_text(strip=True)
        if title.lower().startswith("te huur:"):
            title = title[len("te huur:"):].strip()

        # Plaats staat achter de postcode: "..., 2042LB Zandvoort"
        city = ""
        if "," in title:
            laatste = title.split(",")[-1].strip()      # "2042LB Zandvoort"
            delen = laatste.split(" ", 1)
            city = delen[1].strip() if len(delen) == 2 else laatste

        # Querystring van de URL strippen (die verandert per weergave)
        url = link["href"].split("?")[0]
        if url.startswith("/"):
            url = BASE + url

        price_text = price_el.get_text(strip=True) if price_el else ""
        listings.append({
            "url": url,
            "title": title,
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
            # Ook bij 0 woningen moet de paginastructuur er zijn
            "container_found": "woningaanbod" in response.text,
        },
    }
