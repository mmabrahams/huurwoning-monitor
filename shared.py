"""
Gedeelde functies voor de huurwoning-monitor.
Telegram-berichten, SQLite-database, filters en logging.
"""

import os
import re
import sqlite3
from datetime import datetime

import requests

# --- Laad .env bestand als het bestaat ---
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

# --- Instellingen ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "monitor.log")
DB_FILE = os.path.join(BASE_DIR, "listings.db")

# Maximale huurprijs per maand in euro's
MAX_PRIJS = 1300

# Plaatsen waar we naar zoeken (kleine letters, deelwoorden mogen:
# "santpoort" matcht ook Santpoort-Noord en Santpoort-Zuid)
PLAATSEN = ["haarlem", "heemstede", "santpoort", "overveen"]

# Three-strikes: na zoveel opeenvolgende fouten sturen we een waarschuwing
FAIL_THRESHOLD = 3

# Standaard headers voor het ophalen van websites
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"
}


def log(message):
    """Print een bericht met tijdstip ervoor en schrijf naar logbestand."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {message}"
    print(line)
    try:
        # Houd het logbestand onder de 5 MB
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 5_000_000:
            os.rename(LOG_FILE, LOG_FILE + ".oud")
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def send_telegram(message):
    """Stuur een bericht via Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.ok:
            log("Telegram-bericht verstuurd.")
        else:
            log(f"Telegram-fout: {response.status_code} - {response.text}")
    except Exception as e:
        log(f"Kon Telegram-bericht niet versturen: {e}")


# --- SQLite database ---

def open_db():
    """Open de database en maak de tabellen aan als ze nog niet bestaan."""
    db = sqlite3.connect(DB_FILE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            url TEXT PRIMARY KEY,
            site TEXT,
            title TEXT,
            city TEXT,
            price TEXT,
            first_seen TEXT,
            notified INTEGER DEFAULT 0,
            price_eur INTEGER
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS site_status (
            site TEXT PRIMARY KEY,
            fail_count INTEGER DEFAULT 0,
            last_ok TEXT,
            last_page_size INTEGER
        )
    """)
    # Migratie: voeg de prijs-kolom toe aan een oudere database
    try:
        db.execute("ALTER TABLE listings ADD COLUMN price_eur INTEGER")
    except sqlite3.OperationalError:
        pass  # Kolom bestaat al
    # Vul ontbrekende prijzen aan vanuit de opgeslagen prijstekst
    rows = db.execute(
        "SELECT url, price FROM listings WHERE price_eur IS NULL AND price != ''"
    ).fetchall()
    for url, price_text in rows:
        prijs = parse_prijs(price_text)
        if prijs is not None:
            db.execute("UPDATE listings SET price_eur = ? WHERE url = ?", (prijs, url))
    db.commit()
    return db


def merge_db(other_path):
    """
    Neem alle listings uit een andere database (bijv. uit de cloud) over
    die we lokaal nog niet kennen. Zo voorkomen we dubbele Telegram-berichten
    als het cloud-vangnet heeft gedraaid terwijl de Mac uit stond.
    """
    if not os.path.exists(other_path):
        return 0
    db = open_db()
    try:
        db.execute("ATTACH DATABASE ? AS cloud", (other_path,))
        before = db.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        db.execute("""
            INSERT OR IGNORE INTO listings
                (url, site, title, city, price, first_seen, notified, price_eur)
            SELECT url, site, title, city, price, first_seen, notified, price_eur
            FROM cloud.listings
        """)
        after = db.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        db.commit()
        overgenomen = after - before
        if overgenomen:
            log(f"State-sync: {overgenomen} listing(s) uit de cloud overgenomen")
        return overgenomen
    except sqlite3.Error as e:
        log(f"State-sync: kon cloud-database niet samenvoegen: {e}")
        return 0
    finally:
        db.close()


def site_is_new(db, site):
    """True als we deze site nog nooit succesvol gescraped hebben (eerste run)."""
    row = db.execute(
        "SELECT COUNT(*) FROM listings WHERE site = ?", (site,)
    ).fetchone()
    if row[0] > 0:
        return False
    # Ook geen eerdere succesvolle run geregistreerd?
    row = db.execute(
        "SELECT last_ok FROM site_status WHERE site = ?", (site,)
    ).fetchone()
    return row is None or row[0] is None


def get_bekende_listing(db, url):
    """
    Zoek een eerder geziene listing op.
    Geeft (price_eur, notified) terug, of None als de URL onbekend is.
    """
    row = db.execute(
        "SELECT price_eur, notified FROM listings WHERE url = ?", (url,)
    ).fetchone()
    return row


def bewaar_listing(db, site, listing, notified):
    """Sla een listing op in de database (dedupliceert op URL)."""
    db.execute(
        "INSERT OR IGNORE INTO listings "
        "(url, site, title, city, price, first_seen, notified, price_eur) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (listing["url"], site, listing.get("title", ""), listing.get("city", ""),
         listing.get("price_text", ""), datetime.now().isoformat(),
         1 if notified else 0, listing.get("price_eur")),
    )


def update_listing_prijs(db, url, price_eur, price_text, notified=None):
    """Werk de prijs van een bekende listing bij (bijv. na een prijswijziging)."""
    if notified is None:
        db.execute(
            "UPDATE listings SET price_eur = ?, price = ? WHERE url = ?",
            (price_eur, price_text, url))
    else:
        db.execute(
            "UPDATE listings SET price_eur = ?, price = ?, notified = ? WHERE url = ?",
            (price_eur, price_text, 1 if notified else 0, url))


def get_fail_count(db, site):
    row = db.execute(
        "SELECT fail_count FROM site_status WHERE site = ?", (site,)
    ).fetchone()
    return row[0] if row else 0


def set_status(db, site, fail_count, page_size=None, success=False):
    """Werk de status van een site bij (fail-teller, laatste succes)."""
    db.execute(
        "INSERT INTO site_status (site, fail_count) VALUES (?, 0) "
        "ON CONFLICT(site) DO NOTHING", (site,))
    if success:
        db.execute(
            "UPDATE site_status SET fail_count = ?, last_ok = ?, last_page_size = ? "
            "WHERE site = ?",
            (fail_count, datetime.now().isoformat(), page_size, site))
    else:
        db.execute(
            "UPDATE site_status SET fail_count = ? WHERE site = ?",
            (fail_count, site))
    db.commit()


# --- Filters ---

def parse_prijs(text):
    """
    Haal het prijsbedrag (hele euro's) uit een tekst.
    Werkt met formaten als '€ 1.950,- /mnd', '2.750- excl.', '€7.950 p.m.'
    Geeft None terug als er geen prijs te vinden is.
    """
    if not text:
        return None
    # Zoek getallen zoals 1.950 of 950 (met eventueel ,00 erachter)
    match = re.search(r"(\d{1,3}(?:\.\d{3})+|\d{3,6})(?:,\d+)?", text)
    if not match:
        return None
    return int(match.group(1).replace(".", ""))


def plaats_ok(text):
    """True als de tekst een van de gezochte plaatsen bevat."""
    lower = (text or "").lower()
    return any(plaats in lower for plaats in PLAATSEN)


def prijs_ok(prijs_eur):
    """
    True als de prijs binnen het budget valt.
    Onbekende prijs (None) laten we door: liever een melding te veel dan
    een woning missen.
    """
    return prijs_eur is None or prijs_eur <= MAX_PRIJS


def format_telegram_message(listing, site_label):
    """Maak een mooi Telegram-bericht voor een nieuwe huurwoning."""
    parts = [
        "🏠 <b>Nieuwe huurwoning!</b>",
        "",
        f"<b>{listing['title']}</b>",
        f"📍 {listing.get('city', '')}",
    ]
    if listing.get("price_text"):
        parts.append(f"💰 {listing['price_text']}")
    parts.append("")
    parts.append(f"🔗 <a href=\"{listing['url']}\">Bekijk de woning</a>")
    parts.append("")
    parts.append(f"— {site_label}")
    return "\n".join(parts)


def format_prijsdaling_message(listing, oude_prijs, site_label):
    """Maak een Telegram-bericht voor een prijsverlaging tot binnen budget."""
    parts = [
        "📉 <b>Prijsverlaging - nu binnen je budget!</b>",
        "",
        f"<b>{listing['title']}</b>",
        f"📍 {listing.get('city', '')}",
        f"💰 {listing.get('price_text', '')} (was € " + f"{oude_prijs:,}".replace(",", ".") + ")",
        "",
        f"🔗 <a href=\"{listing['url']}\">Bekijk de woning</a>",
        "",
        f"— {site_label}",
    ]
    return "\n".join(parts)
