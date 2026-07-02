#!/bin/bash
# Dit script wordt elke 5 minuten door launchd gedraaid
cd "/Users/miquel/Claude appjes/Privé/huurwoning-monitor"

REPO_URL="https://github.com/mmabrahams/huurwoning-monitor.git"

# Houd de launchd-logbestanden klein (max ~5 MB)
for f in launchd_out.log launchd_err.log; do
    if [ -f "$f" ] && [ "$(stat -f%z "$f")" -gt 5000000 ]; then
        tail -c 1000000 "$f" > "$f.tmp" && mv "$f.tmp" "$f"
    fi
done

# Stap 1: haal de cloud-database op en voeg onbekende listings samen
# (zodat we geen dubbel bericht sturen over iets dat de cloud al zag).
# Mislukt dit (bijv. geen internet), dan draaien we gewoon lokaal door.
if git fetch origin state 2>/dev/null; then
    if git show origin/state:listings.db > /tmp/cloud_listings.db 2>/dev/null; then
        /usr/bin/python3 merge_cloud.py /tmp/cloud_listings.db
        rm -f /tmp/cloud_listings.db
    fi
fi

# Stap 2: draai de monitor
/usr/bin/python3 monitor.py
STATUS=$?

# Stap 3: push hartslag + database naar GitHub (alleen na een geslaagde run)
# De cloud-watchdog leest deze hartslag om te zien of de Mac nog draait.
if [ $STATUS -eq 0 ]; then
    TMPDIR_STATE=$(mktemp -d)
    cp listings.db "$TMPDIR_STATE/" 2>/dev/null
    date -u +"%Y-%m-%dT%H:%M:%S+00:00" > "$TMPDIR_STATE/heartbeat.txt"
    (
        cd "$TMPDIR_STATE" &&
        git init -q -b state &&
        git add . &&
        git -c user.name="mac-monitor" -c user.email="mac@local" commit -qm "State van Mac $(date '+%Y-%m-%d %H:%M:%S')" &&
        git push -q -f "$REPO_URL" state
    ) 2>/dev/null || echo "State-push naar GitHub mislukt (geen internet?), volgende keer opnieuw."
    rm -rf "$TMPDIR_STATE"
fi

exit $STATUS
