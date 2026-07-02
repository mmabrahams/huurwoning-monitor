"""
Scraper voor Verhuur met Koops (verhuurmetkoops.nl).
De pagina toont woningkaarten als <article class="blog-item">.
"""

import os
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import log, HEADERS, parse_prijs

SITE_NAME = "koops"
SITE_LABEL = "Verhuur met Koops"
URL = "https://www.verhuurmetkoops.nl/huizen-te-huur"
BASE = "https://www.verhuurmetkoops.nl"


def fetch_listings():
    log(f"[{SITE_NAME}] Pagina ophalen: {URL}")
    response = requests.get(URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    page_size = len(response.text)

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("article.blog-item")

    listings = []
    for card in cards:
        title_el = card.select_one(".blog-title")
        link = card.find("a", href=True)
        if not title_el or not link:
            continue
        title = title_el.get_text(strip=True)
        excerpt = card.select_one(".blog-excerpt")
        excerpt_text = excerpt.get_text(strip=True) if excerpt else ""

        # Titel is bijv. "Patiëntiestraat 7-rd, Haarlem" - plaats na de komma
        city = title.split(",")[-1].strip() if "," in title else ""
        prijs = parse_prijs(excerpt_text)

        url = link["href"]
        if url.startswith("/"):
            url = BASE + url

        listings.append({
            "url": url,
            "title": title,
            "city": city,
            "price_text": f"€ {prijs:,}".replace(",", ".") + " p.m." if prijs else excerpt_text,
            "price_eur": prijs,
        })

    log(f"[{SITE_NAME}] {len(listings)} listings gevonden")
    return {
        "listings": listings,
        "health": {
            "page_size": page_size,
            "container_found": len(cards) > 0,
        },
    }
