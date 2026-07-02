"""
Scraper voor 123Wonen (123wonen.nl), vestiging Haarlem.
De vestigingspagina toont de hele regio (ook Heemstede, Aerdenhout,
Hoofddorp, ...) - het plaatsfilter van de monitor doet de rest.
Kaarten zijn <div class="pandlist-container"> en staan gewoon in de HTML.
"""

import os
import re
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import log, HEADERS, parse_prijs

SITE_NAME = "123wonen"
SITE_LABEL = "123Wonen"
URL = "https://www.123wonen.nl/huurwoningen/van/haarlem"

# Kaarten met deze status slaan we over: die woning is al weg
SKIP_STATUS = ["verhuurd", "onder optie", "verkocht"]


def fetch_listings():
    log(f"[{SITE_NAME}] Pagina ophalen: {URL}")
    response = requests.get(URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    page_size = len(response.text)

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("div.pandlist-container")

    listings = []
    for card in cards:
        status_el = card.select_one(".pand-status")
        status = status_el.get_text(strip=True).lower() if status_el else ""
        if any(skip in status for skip in SKIP_STATUS):
            continue

        # URL staat in onclick="location.href='...'" of in een losse link
        url = None
        onclick = card.get("onclick", "")
        match = re.search(r"location\.href='([^']+)'", onclick)
        if match:
            url = match.group(1)
        else:
            link = card.find("a", href=True)
            if link:
                url = link["href"]
        if not url:
            continue

        # Titel is bijv. "Haarlem, <span>Gravinnesteeg</span>" - plaats eerst
        title_el = card.select_one(".pand-title")
        address_el = card.select_one(".pand-address")
        title_text = title_el.get_text(" ", strip=True) if title_el else "Onbekend"
        city = title_text.split(",")[0].strip() if "," in title_text else ""
        address = address_el.get_text(strip=True) if address_el else title_text

        price_el = card.select_one(".pand-price")
        price_text = price_el.get_text(" ", strip=True) if price_el else ""

        listings.append({
            "url": url,
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
            "container_found": "pandlist" in response.text,
        },
    }
