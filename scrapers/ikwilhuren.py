"""
Scraper voor ikwilhuren.nu (MVGM), aanbod gemeente Haarlem.
Kaarten zijn <div class="card-woning">. De pagina heeft paginering
(?page=1, ?page=2, ...); we volgen maximaal MAX_PAGES pagina's.
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
MAX_PAGES = 5


def parse_page(html):
    """Haal de listings van één pagina-HTML."""
    soup = BeautifulSoup(html, "html.parser")
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

    # Zoek links naar volgende pagina's
    page_links = set()
    for a in soup.find_all("a", href=True):
        if "?page=" in a["href"]:
            page_links.add(a["href"])

    return listings, len(cards) > 0, page_links


def fetch_listings():
    log(f"[{SITE_NAME}] Pagina ophalen: {URL}")
    response = requests.get(URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    page_size = len(response.text)

    listings, container_found, page_links = parse_page(response.text)

    # Volg de pagineringslinks (maximaal MAX_PAGES extra pagina's)
    seen_pages = {URL}
    for href in sorted(page_links)[:MAX_PAGES]:
        page_url = BASE + href if href.startswith("/") else href
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        try:
            r = requests.get(page_url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            extra, _, _ = parse_page(r.text)
            listings.extend(extra)
        except Exception as e:
            log(f"[{SITE_NAME}] Kon vervolgpagina niet ophalen ({page_url}): {e}")

    # Ontdubbel binnen deze run (pagina 0 en 1 kunnen hetzelfde zijn)
    unique = {}
    for l in listings:
        unique[l["url"]] = l
    listings = list(unique.values())

    log(f"[{SITE_NAME}] {len(listings)} listings gevonden")
    return {
        "listings": listings,
        "health": {
            "page_size": page_size,
            "container_found": container_found,
        },
    }
