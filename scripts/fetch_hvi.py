"""Refresh data/reference/nyc_hvi_zcta.csv with the full NYC HVI table (all ZCTAs).

Source: NYC Open Data dataset 4mhf-duep (fields zcta20, hvi). Public endpoint, no key needed.
Usage: python scripts/fetch_hvi.py
"""
import csv
import json
import urllib.request
from pathlib import Path

URL = "https://data.cityofnewyork.us/resource/4mhf-duep.json?$limit=5000&$order=zcta20"
OUT = Path(__file__).resolve().parents[1] / "data" / "reference" / "nyc_hvi_zcta.csv"


def main():
    with urllib.request.urlopen(URL, timeout=30) as resp:
        rows = json.loads(resp.read().decode("utf-8"))
    cleaned = sorted({(r["zcta20"], int(r["hvi"])) for r in rows if r.get("zcta20") and r.get("hvi")})
    if not cleaned:
        raise SystemExit("No rows returned; leaving the existing file untouched.")
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["zcta20", "hvi"])
        w.writerows(cleaned)
    print(f"wrote {len(cleaned)} rows to {OUT}")


if __name__ == "__main__":
    main()
