"""
Testscript: simuleert een nieuwe huurwoning en stuurt een echt
Telegram-bericht, zodat je kunt zien hoe een melding eruitziet.
De nepwoning wordt NIET in de database opgeslagen.

Gebruik:  python3 simuleer_listing.py
"""

from shared import send_telegram, format_telegram_message, plaats_ok, prijs_ok

nep_listing = {
    "url": "https://www.voorbeeld.nl/woning/kruisstraat-1",
    "title": "Kruisstraat 1, Haarlem",
    "city": "Haarlem",
    "price_text": "€ 1.250,- per maand",
    "price_eur": 1250,
}

# Controleer dat de filters deze woning zouden doorlaten
assert plaats_ok(nep_listing["city"]), "Plaats-filter zou deze woning blokkeren!"
assert prijs_ok(nep_listing["price_eur"]), "Prijs-filter zou deze woning blokkeren!"

print("Filters OK - testbericht versturen...")
send_telegram(format_telegram_message(nep_listing, "TESTBERICHT (simulatie)"))
print("Klaar! Check je Telegram.")
