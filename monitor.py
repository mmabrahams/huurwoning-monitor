"""
Huurwoning Monitor Haarlem e.o. - Hoofdscript
Checkt vijf verhuursites op nieuwe huurwoningen in Haarlem, Heemstede,
Santpoort en Overveen tot 1.300 euro per maand, en stuurt een
Telegram-bericht bij elke nieuwe woning.

Deduplicatie gaat via SQLite (listings.db) op listing-URL.
Eerste run per site = seeden zonder notificaties.
Eén kapotte site blokkeert de rest niet (try/except per site).
"""

import traceback

from shared import (
    log, send_telegram, open_db, site_is_new, get_bekende_listing,
    bewaar_listing, update_listing_prijs, get_fail_count, set_status,
    plaats_ok, prijs_ok, format_telegram_message, format_prijsdaling_message,
    FAIL_THRESHOLD, MAX_PRIJS,
)

from scrapers import (
    koops, rotsvast, wbos, ikwilhuren, vesteda, wonen123, interhouse,
    hre, centraal, nuwoonruimte,
)

SITES = [koops, rotsvast, wbos, ikwilhuren, vesteda, wonen123, interhouse,
         hre, centraal, nuwoonruimte]


def handle_failure(db, site, error_message):
    """Verwerk een gefaalde check met de three-strikes-regel."""
    name, label = site.SITE_NAME, site.SITE_LABEL
    fail_count = get_fail_count(db, name) + 1
    log(f"[{name}] Fout #{fail_count}: {error_message}")

    if fail_count == FAIL_THRESHOLD:
        send_telegram(
            f"⚠️ <b>{label} faalt al {FAIL_THRESHOLD}x achter elkaar!</b>\n\n"
            f"Laatste fout: {error_message}\n\n"
            f"De monitor blijft het proberen. Je krijgt bericht zodra het weer werkt."
        )
    set_status(db, name, fail_count)


def handle_recovery(db, site):
    """Stuur een hersteld-bericht als de site eerder bleef falen."""
    name, label = site.SITE_NAME, site.SITE_LABEL
    previous_fails = get_fail_count(db, name)
    if previous_fails >= FAIL_THRESHOLD:
        send_telegram(
            f"✅ <b>{label} werkt weer!</b>\n\n"
            f"Na {previous_fails} mislukte pogingen is de site weer bereikbaar."
        )
        log(f"[{name}] Hersteld na {previous_fails} fouten")


def check_prijsdaling(db, label, listing, bekend, eerste_run):
    """
    Vergelijk de prijs van een al bekende listing met wat we eerder zagen.
    Zakt de prijs van boven naar binnen het budget, dan sturen we alsnog
    een bericht (de woning was eerder te duur en dus nooit gemeld).
    """
    oude_prijs, _ = bekend
    nieuwe_prijs = listing.get("price_eur")

    if nieuwe_prijs is None or nieuwe_prijs == oude_prijs:
        return

    in_regio = plaats_ok(listing.get("city", "") + " " + listing.get("title", ""))
    zakt_binnen_budget = (oude_prijs is not None
                          and oude_prijs > MAX_PRIJS
                          and nieuwe_prijs <= MAX_PRIJS)

    if zakt_binnen_budget and in_regio and not eerste_run:
        send_telegram(format_prijsdaling_message(listing, oude_prijs, label))
        log(f"PRIJSVERLAGING GEMELD: {listing['title']} "
            f"van €{oude_prijs} naar €{nieuwe_prijs}")
        update_listing_prijs(db, listing["url"], nieuwe_prijs,
                             listing.get("price_text", ""), notified=True)
    else:
        log(f"Prijswijziging (geen melding): {listing['title']} "
            f"van €{oude_prijs} naar €{nieuwe_prijs}")
        update_listing_prijs(db, listing["url"], nieuwe_prijs,
                             listing.get("price_text", ""))


def check_site(db, site):
    """Check één site op nieuwe woningen. Geeft True terug als het gelukt is."""
    name, label = site.SITE_NAME, site.SITE_LABEL
    log(f"--- {label} ---")

    try:
        result = site.fetch_listings()
        listings = result["listings"]
        health = result["health"]

        # Gezondheidscheck: verwachte structuur aanwezig?
        if not health.get("container_found"):
            handle_failure(db, site,
                           "Verwachte HTML-structuur niet gevonden (site mogelijk gewijzigd)")
            return False

        handle_recovery(db, site)

        eerste_run = site_is_new(db, name)
        if eerste_run:
            log(f"[{name}] EERSTE RUN - baseline opslaan, geen notificaties")

        nieuw = 0
        for listing in listings:
            bekend = get_bekende_listing(db, listing["url"])
            if bekend is not None:
                check_prijsdaling(db, label, listing, bekend, eerste_run)
                continue
            nieuw += 1

            # Filters: alleen melden bij juiste plaats en prijs
            in_regio = plaats_ok(listing.get("city", "") + " " + listing.get("title", ""))
            binnen_budget = prijs_ok(listing.get("price_eur"))
            melden = in_regio and binnen_budget and not eerste_run

            if melden:
                send_telegram(format_telegram_message(listing, label))
                log(f"[{name}] NIEUW & GEMELD: {listing['title']} - {listing.get('price_text')}")
            else:
                reden = ("eerste run" if eerste_run
                         else "buiten regio" if not in_regio
                         else f"boven €{MAX_PRIJS}")
                log(f"[{name}] Nieuw maar niet gemeld ({reden}): "
                    f"{listing['title']} - {listing.get('price_text')}")

            bewaar_listing(db, name, listing, notified=melden)

        db.commit()
        if nieuw == 0:
            log(f"[{name}] Geen nieuwe listings.")

        set_status(db, name, fail_count=0,
                   page_size=health.get("page_size"), success=True)
        return True

    except Exception as e:
        handle_failure(db, site, f"{type(e).__name__}: {e}")
        return False


def main():
    log("=== Huurwoning Monitor Haarlem e.o. - Start ===")
    db = open_db()

    results = {}
    for site in SITES:
        try:
            results[site.SITE_NAME] = check_site(db, site)
        except Exception as e:
            # Vangnet voor fouten die check_site zelf niet afving
            log(f"[{site.SITE_NAME}] Onverwachte kritieke fout: {e}")
            log(traceback.format_exc())
            results[site.SITE_NAME] = False

    db.close()
    ok = sum(1 for v in results.values() if v)
    fail = len(results) - ok
    log(f"=== Klaar: {ok} sites OK, {fail} gefaald ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_text = traceback.format_exc()
        print(f"KRITIEKE FOUT: {error_text}")
        try:
            send_telegram(
                f"🚨 <b>Huurwoning-monitor compleet gecrasht!</b>\n\n"
                f"<pre>{error_text[-800:]}</pre>"
            )
        except Exception:
            pass
