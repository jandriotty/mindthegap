# mindthegap

Health in Climate AI Hackathon, NYC 2026: *Reaching high-risk New Yorkers before climate emergencies* (NYC Department of Health and Mental Hygiene).

**Status:** early build. All data in this repo is synthetic. No real patient data.

## Layout
```
mindthegap/
├── README.md
├── requirements.txt
├── .env.example          copy to .env (git-ignored) and add your key
├── data/                 see data/README.md
│   └── synthetic/
│       ├── clients/      10 fictional client records (JSON with provenance + flat CSV)
│       └── heat_events/  one synthetic NYC heat-wave week (hourly, daily, alerts, forecasts)
├── src/                  intake and rule engine code
├── app/                  Streamlit UI
├── tests/
└── docs/                 notes, specs, evidence
```

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env
```

## Regenerate the synthetic data
```bash
python data/synthetic/clients/generate_synthetic_clients.py
python data/synthetic/heat_events/generate_heat_events.py
```
Both are deterministic and re-run their own consistency checks.
