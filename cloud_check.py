"""
Cloud-vangnet + watchdog. Draait elke ~10 minuten op GitHub Actions.

Werking:
1. Lees heartbeat.txt - de "hartslag" die de Mac na elke succesvolle
   run naar GitHub pusht.
2. Is de hartslag vers (jonger dan MAX_LEEFTIJD_MIN)? Dan draait de Mac
   prima en doet de cloud niets.
3. Is de hartslag oud of ontbreekt hij? Dan is de Mac-monitor gestopt:
   - stuur eenmalig een waarschuwing via Telegram (max 1x per 24 uur),
   - en draai de monitor hier in de cloud, zodat je niets mist.

De cloud werkt met dezelfde database (listings.db van de state-branch),
dus je krijgt geen dubbele berichten als de Mac later weer aan gaat.
"""

import sys
from datetime import datetime, timedelta, timezone

from shared import log, send_telegram

# Na hoeveel minuten stilte we de Mac als "gestopt" beschouwen.
# De Mac draait elke 5 minuten; 25 minuten = 5 gemiste runs.
MAX_LEEFTIJD_MIN = 25

# Hoe vaak we maximaal waarschuwen dat de Mac uit staat
WAARSCHUWING_INTERVAL_UREN = 24


def lees_tijdstip(pad):
    """Lees een ISO-tijdstip uit een bestand. None als het niet lukt."""
    try:
        with open(pad) as f:
            tekst = f.read().strip().replace("Z", "+00:00")
        tijd = datetime.fromisoformat(tekst)
        if tijd.tzinfo is None:
            tijd = tijd.replace(tzinfo=timezone.utc)
        return tijd
    except Exception:
        return None


def main():
    nu = datetime.now(timezone.utc)
    hartslag = lees_tijdstip("heartbeat.txt")

    if hartslag and nu - hartslag < timedelta(minutes=MAX_LEEFTIJD_MIN):
        minuten = int((nu - hartslag).total_seconds() // 60)
        log(f"Mac draait prima (hartslag {minuten} min geleden). Cloud doet niets.")
        sys.exit(0)

    # De Mac is stil - waarschuw (maar niet vaker dan 1x per 24 uur)
    laatste_waarschuwing = lees_tijdstip("alert.txt")
    if (laatste_waarschuwing is None
            or nu - laatste_waarschuwing > timedelta(hours=WAARSCHUWING_INTERVAL_UREN)):
        if hartslag:
            minuten = int((nu - hartslag).total_seconds() // 60)
            wanneer = f"{minuten} minuten geleden"
        else:
            wanneer = "onbekend (geen hartslag gevonden)"
        send_telegram(
            "⚠️ <b>De monitor op je Mac lijkt gestopt!</b>\n\n"
            f"Laatste hartslag: {wanneer}.\n\n"
            "Het cloud-vangnet neemt het over totdat je Mac weer draait. "
            "Berichten komen dan iets trager (elke ~10 minuten). "
            "Staat je Mac expres uit? Dan hoef je niets te doen."
        )
        with open("alert.txt", "w") as f:
            f.write(nu.isoformat())

    # Draai de monitor in de cloud als vangnet
    log("Cloud-vangnet actief: monitor draaien op GitHub Actions.")
    import monitor
    monitor.main()


if __name__ == "__main__":
    main()
