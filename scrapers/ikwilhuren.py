"""
Scraper voor ikwilhuren.nu (MVGM), aanbod gemeente Haarlem.
Kaarten zijn <div class="card-woning">.

LET OP: deze site heeft een strenge beveiligingsbot. Op 21 juli 2026
blokkeerde die ons IP-adres omdat we elke 5 minuten tot 6 pagina's
ophaalden. Daarom doen we het nu heel rustig aan:
- alleen de eerste pagina (daar staan de nieuwste woningen), en
- maximaal 1x per uur (via CHECK_INTERVAL_MIN, zie monitor.py).
"""

import os
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import log, HEADERS, parse_prijs

SITE_NAME = "ikwilhuren"
SITE_LABEL = "ikwilhuren.nu"
URL = "https://ikwilhuren.nu/aanbod/haarlem"
BASE = "https://ikwilhuren.nu"

# Maximaal 1x per uur checken - de beveiligingsbot van deze site is streng
CHECK_INTERVAL_MIN = 60


def fetch_listings():
    log(f"[{SITE_NAME}] Pagina ophalen: {URL}")
    response = requests.get(URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    page_size = len(response.text)

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("div.card-woning")

    listings = []
    for card in cards:
        link = card.select_one("a.stretched-link")
        if not link:
            continue
        title = link.get_text(strip=True)

        # Locatie-regel is bijv. "2014SL Haarlem - 2Km."
        city = ""
        spans = card.select(".card-body > span")
        if len(spans) > 1:
            loc = spans[1].get_text(strip=True)
            city = loc.split("-")[0].strip()  # "2014SL Haarlem"

        price_el = card.select_one(".fw-bold")
        price_text = price_el.get_text(strip=True) if price_el else ""

        url = link["href"]
        if url.startswith("/"):
            url = BASE + url

        listings.append({
            "url": url,
            "title": title,
            "city": city,
            "price_text": price_text,
            "price_eur": parse_prijs(price_text),
        })

    log(f"[{SITE_NAME}] {len(listings)} listings gevonden (alleen pagina 1)")
    return {
        "listings": listings,
        "health": {
            "page_size": page_size,
            "container_found": len(cards) > 0,
        },
    }
