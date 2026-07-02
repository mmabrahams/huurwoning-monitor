# Huurwoning Monitor Haarlem e.o.

Checkt elke 5 minuten vijf verhuursites op nieuwe huurwoningen in
**Haarlem, Heemstede, Santpoort en Overveen** tot **€ 1.300 per maand**,
en stuurt een Telegram-bericht bij elke nieuwe woning (adres, plaats,
prijs en link).

## Welke sites?

| Site | Hoe |
|---|---|
| Verhuur met Koops | HTML-pagina |
| Rotsvast | Zoekpagina `/huren/?search=Haarlem&radius=10` (de oude woningaanbod-URL bestaat niet meer) |
| WBOS Makelaars | HTML-pagina (al verhuurde woningen worden overgeslagen) |
| ikwilhuren.nu | HTML-pagina's, met paginering |
| Vesteda | JSON-API (de woningen staan niet in de HTML) |

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
- `listings.db` - SQLite-database met alle geziene woningen
- `.env` - Telegram-token en chat-id (zelfde bot als de antikraak-monitor)
- `monitor.log` - logboek (wordt automatisch klein gehouden)

## Later toevoegen: 123wonen.nl en interhouse.nl

Deze sites laden hun woningen met JavaScript; daarvoor moeten we hun
JSON-endpoints gebruiken (zelfde aanpak als bij Vesteda). Nieuwe site
toevoegen = nieuw bestand in `scrapers/` + één regel in de
`SITES`-lijst in `monitor.py`. De eerste run seedt dan automatisch
zonder berichten.
