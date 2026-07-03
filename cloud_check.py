"""
Cloud-vangnet + watchdog. Draait elke ~10 minuten op GitHub Actions.

Werking:
1. Lees heartbeat.txt - de "hartslag" die de Mac na elke succesvolle
   run naar GitHub pusht.
2. Is de hartslag vers (jonger dan MAX_LEEFTIJD_MIN)? Dan draait de Mac
   prima en doet de cloud niets.
3. Is de hartslag oud of ontbreekt hij? Dan draait de Mac niet:
   - de cloud draait de monitor zelf, zodat je niets mist;
   - en je krijgt een waarschuwing via Telegram, MAAR:
     * niet tijdens de stille uren (22:00 - 09:00 Nederlandse tijd),
       want een Mac die 's nachts slaapt is normaal;
     * en maximaal 1x per 24 uur (bijgehouden in alert.txt).

De cloud werkt met dezelfde database (listings.db van de state-branch),
dus je krijgt geen dubbele berichten als de Mac later weer aan gaat.
"""

import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from shared import log, send_telegram

# Na hoeveel minuten stilte we de Mac als "gestopt" beschouwen.
# De Mac draait elke 5 minuten; 25 minuten = 5 gemiste runs.
MAX_LEEFTIJD_MIN = 25

# Hoe vaak we maximaal waarschuwen dat de Mac uit staat
WAARSCHUWING_INTERVAL_UREN = 24

# Stille uren (Nederlandse tijd): geen waarschuwingen, wel stil doordraaien
STIL_VANAF = 22   # vanaf 22:00 's avonds
STIL_TOT = 9      # tot 09:00 's ochtends


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


def in_stille_uren(nu):
    """True tussen 22:00 en 09:00 Nederlandse tijd."""
    lokaal = nu.astimezone(ZoneInfo("Europe/Amsterdam"))
    return lokaal.hour >= STIL_VANAF or lokaal.hour < STIL_TOT


def beslis(nu, hartslag, laatste_waarschuwing):
    """
    Bepaal wat de cloud moet doen. Geeft één van deze strings terug:
    - "niets"              : Mac draait prima
    - "vangnet"            : monitor draaien, geen waarschuwing
    - "vangnet+waarschuwing": monitor draaien én waarschuwen
    """
    if hartslag and nu - hartslag < timedelta(minutes=MAX_LEEFTIJD_MIN):
        return "niets"

    if in_stille_uren(nu):
        return "vangnet"  # 's nachts slapen is normaal

    if (laatste_waarschuwing is not None
            and nu - laatste_waarschuwing < timedelta(hours=WAARSCHUWING_INTERVAL_UREN)):
        return "vangnet"  # al recent gewaarschuwd

    return "vangnet+waarschuwing"


def main():
    nu = datetime.now(timezone.utc)
    hartslag = lees_tijdstip("heartbeat.txt")
    laatste_waarschuwing = lees_tijdstip("alert.txt")

    actie = beslis(nu, hartslag, laatste_waarschuwing)

    if actie == "niets":
        minuten = int((nu - hartslag).total_seconds() // 60)
        log(f"Mac draait prima (hartslag {minuten} min geleden). Cloud doet niets.")
        sys.exit(0)

    if actie == "vangnet+waarschuwing":
        if hartslag:
            minuten = int((nu - hartslag).total_seconds() // 60)
            wanneer = f"{minuten} minuten geleden"
        else:
            wanneer = "onbekend (geen hartslag gevonden)"
        send_telegram(
            "⚠️ <b>De monitor op je Mac lijkt gestopt!</b>\n\n"
            f"Laatste hartslag: {wanneer}.\n\n"
            "Het cloud-vangnet neemt het over totdat je Mac weer draait. "
            "Berichten komen dan iets trager. "
            "Staat je Mac expres uit? Dan hoef je niets te doen."
        )
        with open("alert.txt", "w") as f:
            f.write(nu.isoformat())
    else:
        log("Mac is stil, maar geen waarschuwing (stille uren of al recent gewaarschuwd).")

    # Draai de monitor in de cloud als vangnet
    log("Cloud-vangnet actief: monitor draaien op GitHub Actions.")
    import monitor
    monitor.main()


if __name__ == "__main__":
    main()
