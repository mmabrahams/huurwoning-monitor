"""
Scraper voor Centraal Makelaardij (centraalmakelaardij.nl).
De aanbodpagina toont alleen beschikbare woningen (koop én huur) als
<article class="card card__object">. Koopwoningen herkennen we aan
"k.k." of "v.o.n." in de prijs en slaan we over.
"""

import os
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import log, HEADERS, parse_prijs

SITE_NAME = "centraal"
SITE_LABEL = "Centraal Makelaardij"
URL = "https://centraalmakelaardij.nl/aanbod/"


def fetch_listings():
    log(f"[{SITE_NAME}] Pagina ophalen: {URL}")
    response = requests.get(URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    page_size = len(response.text)

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("article.card__object")

    listings = []
    for card in cards:
        link = card.select_one("a.card__overlay") or card.find("a", href=True)
        title_el = card.select_one(".card__title h3")
        place_el = card.select_one(".card__title p")
        price_el = card.select_one(".card__details p")
        if not link or not title_el:
            continue

        price_text = price_el.get_text(strip=True) if price_el else ""
        if "k.k." in price_text or "v.o.n." in price_text:
            continue  # koopwoning

        # Plaatsregel is bijv. "2011 JH, Haarlem, Nederland"
        city = ""
        if place_el:
            delen = [d.strip() for d in place_el.get_text(strip=True).split(",")]
            if len(delen) >= 2:
                city = delen[1]

        title = title_el.get_text(strip=True)
        listings.append({
            "url": link["href"],
            "title": f"{title}, {city}" if city else title,
            "city": city,
            "price_text": price_text,
            "price_eur": parse_prijs(price_text),
        })

    log(f"[{SITE_NAME}] {len(listings)} huurwoningen gevonden "
        f"({len(cards)} kaarten totaal, koop overgeslagen)")
    return {
        "listings": listings,
        "health": {
            "page_size": page_size,
            "container_found": len(cards) > 0,
        },
    }
