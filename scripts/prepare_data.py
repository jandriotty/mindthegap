"""Build public-data snapshots and explicitly synthetic demo clients; stdlib only."""
import argparse, csv, json, urllib.error, urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--clients', type=Path, help='Canonical synthetic client JSON; see docs/06-data-contract.md')
args = parser.parse_args()
OUT = ROOT / 'dist/data'
OUT.mkdir(parents=True, exist_ok=True)

def rows(path):
    with (ROOT / path).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

# Cached snapshots vendored under data-sources/ so this script runs standalone
# from a fresh clone. Re-pull from the source URLs in the payload below if a
# refresh is ever needed.
hvi = rows('data-sources/hvi-nta-2020.csv')
heat = rows('data-sources/heat-ed-visits-datawrapper-snapshot.csv')

def fetch_current_heat_risk():
    """Live NOAA daily-summaries pull for Central Park, no API key required.
    This is an OBSERVED max temperature, not a forecast — unlike
    heatwatch.sydney.edu.au's Excess Heat Factor model, which is calibrated
    to Australian conditions and not something we can honestly borrow for
    NYC. On any network failure this returns available:false rather than
    fabricating a reading; the UI must show a clear unavailable state."""
    end = date.today()
    start = end - timedelta(days=10)
    url = ('https://www.ncei.noaa.gov/access/services/data/v1'
           f'?dataset=daily-summaries&stations=USW00094728&startDate={start}&endDate={end}'
           '&dataTypes=TMAX&format=json&units=standard')
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            observations = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return {'available': False}
    observations = [r for r in observations if r.get('TMAX') not in (None, '')]
    if not observations:
        return {'available': False}
    latest = observations[-1]
    tmax = float(latest['TMAX'])
    # Tier cutoffs at 95/100/105°F follow real NWS New York Heat Advisory /
    # Extreme Heat Warning thresholds (weather.gov/okx/extremeheat). Below
    # that, 80/90 are just readable round-number splits, not an official
    # category — TMAX also stands in for heat index since daily-summaries
    # doesn't carry humidity, so this is a proxy, not the real heat index.
    tiers = [(80, 'Minimal', '#22c55e'), (90, 'Low', '#a3e635'), (95, 'Moderate', '#facc15'),
             (100, 'High', '#fb923c'), (105, 'Severe', '#ef4444')]
    band, color = 'Extreme', '#7f1d4b'
    for threshold, name, hex_color in tiers:
        if tmax < threshold:
            band, color = name, hex_color
            break
    return {
        'available': True, 'date': latest['DATE'], 'tmax_f': tmax, 'band': band, 'color': color,
        'station': 'Central Park, NYC (USW00094728)',
        'source': 'NOAA NCEI daily summaries — observed, not a forecast',
        'source_url': 'https://www.ncei.noaa.gov/access/services/data/v1',
        'threshold_note': 'Band cutoffs at 95/100/105°F follow NWS heat advisory thresholds; TMAX approximates heat index (no humidity data).',
        'threshold_source_url': 'https://www.weather.gov/okx/extremeheat',
    }

heat_risk = fetch_current_heat_risk()
selected = [r for r in hvi if r['NTACode'] in ['BX0101', 'BX0102', 'BX0201', 'BX0202']]
def field(value, checked='2026-09-18'):
    return {'value': value, 'source': 'Project-created synthetic fixture', 'verified_at': checked}
clients = []
for i in range(12):
    unresolved = i < 4
    unknown = 4 <= i < 8
    clients.append({
        'id': f'DEMO-{i+1:03}', 'synthetic': True,
        'nta': field(selected[i % len(selected)]['NTACode']),
        'zip': field('10454' if i % 2 == 0 else '10455'),
        'cohort': field('SMI' if i % 3 else 'SUD'),
        'age': field(28 + i * 3), 'language': field('Spanish' if i % 3 == 0 else 'English'),
        'consent': field('unknown' if i == 7 else 'yes'),
        'cooling': field('broken' if unresolved else 'unknown' if unknown else 'working', None if unknown else '2026-09-18'),
        'backup': field('unknown' if unknown else 'yes'),
        'transport': field('needed' if i < 2 else 'unknown' if unknown else 'no'),
        'affordability': field('unknown' if unknown else 'no'),
        'clinical': field('unknown' if unknown else 'no'),
        'contact': field('unknown' if unknown else 'Phone — demo, no number stored', None if unknown else '2026-09-18'),
        'owner': '', 'outcome': 'Unreachable' if i in [2, 6] else '', 'notes': '',
        'tasks': ([{'type':'Cooling support', 'owner':'Housing staff', 'due':'2026-09-20', 'status':'Requested', 'evidence':''}] if unresolved else []) + ([{'type':'Transportation', 'owner':'Resource partner', 'due':'2026-09-20', 'status':'Requested', 'evidence':''}] if i < 2 else []),
        'history': []
    })
if args.clients:
    imported = json.loads(args.clients.read_text(encoding='utf-8'))
    if not isinstance(imported, list) or not imported:
        raise ValueError('Expected a non-empty array of synthetic client records')
    identifiers = set()
    for c in imported:
        if c.get('synthetic') is not True:
            raise ValueError('This demo accepts synthetic records only')
        if not isinstance(c.get('id'), str) or c['id'] in identifiers:
            raise ValueError('Each client needs a unique string ID')
        identifiers.add(c['id'])
        for name in ['nta','zip','cohort','age','language','consent','cooling','backup','transport','affordability','clinical','contact']:
            if not isinstance(c.get(name),dict) or not all(k in c[name] for k in ['value','source','verified_at']):
                raise ValueError(f'{c["id"]}: {name} must include value, source and verified_at')
        for name, allowed in {'consent':['yes','no','unknown'],'cooling':['working','broken','unavailable','unknown'],'backup':['yes','no','unknown'],'transport':['needed','no','unknown'],'affordability':['yes','no','unknown'],'clinical':['yes','no','unknown']}.items():
            if c[name]['value'] not in allowed:
                raise ValueError(f'{c["id"]}: invalid {name} value')
        c.setdefault('tasks',[])
        c.setdefault('history',[])
        c.setdefault('owner','')
        c.setdefault('outcome','')
        c.setdefault('notes','')
    clients = imported

payload = {
    'hvi': selected, 'hvi_total_rows': len(hvi),
    'hvi_source': 'https://raw.githubusercontent.com/nychealth/EHDP-data/production/key-topics/heat-vulnerability-index/hvi-nta-2020.csv',
    'heat': [r for r in heat if r['END_DATE'].endswith('/24')],
    'heat_source': 'https://datawrapper.dwcdn.net/azZ94/1/dataset.csv',
    'heat_risk': heat_risk,
    'clients': clients,
    'event': {'name': 'Demo heat advisory', 'starts': '2026-09-20', 'ends': '2026-09-22', 'zips':['10454','10455'], 'source':'Simulated event — not an NWS advisory'},
    'decision_table': [
        {'field':'cooling', 'values':['broken','unavailable'], 'task':'Cooling support', 'owner':'Housing staff'},
        {'field':'transport', 'values':['needed'], 'task':'Transportation', 'owner':'Resource partner'},
        {'field':'affordability', 'values':['yes'], 'task':'Cooling affordability', 'owner':'Care navigator'},
        {'field':'clinical', 'values':['yes'], 'task':'Clinical question', 'owner':'Clinician'}
    ]
}
(OUT / 'demo.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
print(f'Prepared {len(selected)} real HVI neighborhoods from {len(hvi)} rows; {len(payload["heat"])} historical heat observations; {len(clients)} synthetic clients.')
