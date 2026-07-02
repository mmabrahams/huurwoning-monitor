"""
Hulpscript: neem listings uit de cloud-database over in de lokale database.
Wordt door run_monitor.sh aangeroepen vóór elke run, zodat de Mac weet
wat het cloud-vangnet al heeft gezien (geen dubbele berichten).

Gebruik:  python3 merge_cloud.py /pad/naar/cloud_listings.db
"""

import sys

from shared import merge_db

if len(sys.argv) > 1:
    merge_db(sys.argv[1])
