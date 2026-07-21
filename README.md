# Huurwoning Monitor Haarlem e.o.

Checkt elke 5 minuten tien verhuursites op nieuwe huurwoningen in
**Haarlem, Heemstede, Santpoort en Overveen** tot **€ 1.300 per maand**,
en stuurt een Telegram-bericht bij elke nieuwe woning (adres, plaats,
prijs en link). Zakt de prijs van een bekende woning tot binnen het
budget, dan krijg je ook een bericht (prijsverlaging).

## Welke sites?

| Site | Hoe |
|---|---|
| Verhuur met Koops | HTML-pagina |
| Rotsvast | Zoekpagina `/huren/?search=Haarlem&radius=10` (de oude woningaanbod-URL bestaat niet meer) |
| WBOS Makelaars | HTML-pagina (al verhuurde woningen worden overgeslagen) |
| ikwilhuren.nu | HTML-pagina, alleen pagina 1, max 1x per uur (hun beveiligingsbot blokkeerde op 21-07-2026 ons IP na 2,5 week elke-5-min-scrapen met 6 pagina's per keer; ontgrendelen kan via de blokkadepagina zelf) |
| Vesteda | JSON-API (de woningen staan niet in de HTML) |
| 123Wonen | Vestigingspagina `/huurwoningen/van/haarlem` (toont hele regio) |
| Interhouse | WordPress-AJAX-endpoint (`building_results_action`, vestiging Haarlem) |
| Haarlem Real Estate | JSON-feed `/en/realtime-listings/consumer` |
| Centraal Makelaardij | HTML-pagina `/aanbod/` (koopwoningen worden overgeslagen) |
| nuWoonruimte | HTML-pagina `/woningaanbod/huur` |

## Cloud-vangnet + watchdog (GitHub Actions)

De monitor draait op je Mac, maar een Mac slaapt weleens. Daarom:

- Na elke geslaagde run pusht de Mac een **hartslag** (tijdstempel) en de
  database naar GitHub (repo `mmabrahams/huurwoning-monitor`, branch `state`).
- **GitHub Actions checkt regelmatig** die hartslag (gepland elke 10 min,
  maar GitHub's planner is grillig - in de praktijk elke 10 min tot enkele
  uren). Is de hartslag ouder dan 25 minuten, dan draait de cloud de
  monitor zelf, tot je Mac terug is.
- Daarbij krijg je een Telegram-waarschuwing, maar met twee remmen:
  **niet tijdens de stille uren (22:00 - 09:00)** - een Mac die 's nachts
  slaapt is normaal, de cloud neemt het dan stil over - en **maximaal 1x
  per 24 uur** (bijgehouden in alert.txt op de state-branch; de Mac
  bewaart dat bestandje bij zijn eigen pushes).
- De cloud gebruikt **dezelfde database**, en de Mac neemt bij het opstarten
  eerst de cloud-vondsten over. Zo krijg je geen dubbele berichten.

Staat je Mac expres uit (vakantie)? Prima - de cloud monitort gewoon door.
De waarschuwing mag je dan negeren.

## Hoe het werkt

- **Deduplicatie**: elke geziene woning-URL wordt opgeslagen in de
  SQLite-database `listings.db`. Alleen woningen met een nog onbekende
  URL leveren een bericht op.
- **Eerste run**: bij de allereerste run per site worden alle bestaande
  woningen stil opgeslagen (geen berichtenregen). Dit gebeurt ook
  automatisch als je later een nieuwe site toevoegt.
- **Filters**: alleen woningen in de juiste plaats én binnen budget
  worden gemeld. Woningen zonder herkenbare prijs worden wél gemeld
  (liever een melding te veel dan een woning missen). Alle instellingen
  staan bovenin `shared.py` (`MAX_PRIJS` en `PLAATSEN`).
- **Foutbestendig**: elke site heeft zijn eigen try/except - als één
  site kapot is, gaan de andere vier gewoon door. Na 3 fouten op rij
  krijg je één waarschuwing via Telegram, en een berichtje zodra de
  site weer werkt.

## Automatisch draaien

De monitor draait elke 5 minuten via launchd (de Mac-versie van cron):
`~/Library/LaunchAgents/com.miquel.huurwoning-monitor.plist`

Handige commando's (in Terminal):

```bash
# Stoppen
launchctl unload ~/Library/LaunchAgents/com.miquel.huurwoning-monitor.plist

# Weer starten
launchctl load ~/Library/LaunchAgents/com.miquel.huurwoning-monitor.plist

# Handmatig één keer draaien
cd "/Users/miquel/Claude appjes/Privé/huurwoning-monitor" && python3 monitor.py

# Testbericht naar Telegram sturen
cd "/Users/miquel/Claude appjes/Privé/huurwoning-monitor" && python3 simuleer_listing.py

# Logboek bekijken
tail -50 "/Users/miquel/Claude appjes/Privé/huurwoning-monitor/monitor.log"
```

## Bestanden

- `monitor.py` - hoofdscript, checkt alle sites
- `shared.py` - instellingen (budget, plaatsen), Telegram, database, filters
- `scrapers/` - één bestand per site
- `cloud_check.py` - watchdog + vangnet, draait alleen op GitHub Actions
- `merge_cloud.py` - neemt cloud-vondsten over in de lokale database
- `listings.db` - SQLite-database met alle geziene woningen
- `.env` - Telegram-token en chat-id (zelfde bot als de antikraak-monitor)
- `monitor.log` - logboek (wordt automatisch klein gehouden)
- `.github/workflows/monitor.yml` - het cloud-vangnet

## Nieuwe site toevoegen

Nieuw bestand in `scrapers/` + één regel in de `SITES`-lijst in
`monitor.py`, en daarna `git push` (zodat de cloud hem ook kent).
De eerste run seedt automatisch zonder berichtenregen.

Onderzocht en afgevallen (juli 2026):

| Site | Reden |
|---|---|
| huurwoningen.nl / Pararius | Blokkeren geautomatiseerde verzoeken (HTTP 403) |
| Wado (Van Waalwijk van Doorn) | Aanbod is alleen koop; huur-filter werkt niet server-side |
| JRS Makelaars | Vrijwel alleen koopwoningen |
| PUUR Verhuur & Beheer | Eigen site toont geen huuraanbod (adverteren via Pararius) |
| Koops Makelaardij | Zelfde bedrijf als Verhuur met Koops (al in de monitor) |
