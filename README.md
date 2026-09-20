# mindthegap

Health in Climate AI Hackathon, NYC 2026: *Reaching high-risk New Yorkers before climate emergencies* (NYC Department of Health and Mental Hygiene).

**Status:** early build. All data in this repo is synthetic. No real patient data.

## Layout
```
mindthegap/
├── README.md
├── requirements.txt
├── .env.example          copy to .env (git-ignored) and add your key
├── config/               rule engine settings: weights, bands, ICD map, drug classes (all defaults)
├── data/                 see data/README.md
│   ├── synthetic/
│   │   ├── clients/      10 fictional client records (JSON with provenance + flat CSV)
│   │   └── heat_events/  one synthetic NYC heat-wave week (hourly, daily, alerts, forecasts)
│   └── reference/        NYC Heat Vulnerability Index by ZIP (subset)
├── src/mindthegap/       rule engine (config, data loading, factors, hazard, scoring, CLI)
├── scripts/              run_engine.py, print_weights.py, fetch_hvi.py
├── app/                  Streamlit UI (not built yet)
├── tests/                engine tests
└── docs/                 rule-engine.md: how scores are computed, weights, limits
```

## Rule engine
A transparent, hand-weighted points scorecard (not a decision tree, not machine learning) that combines
client factors, the heat hazard as of a chosen moment, and the neighborhood HVI into a risk score **range**
with a separate **confidence**. **Weights are defaults, not calibrated: tune with clinicians.**
Details: [docs/rule-engine.md](docs/rule-engine.md).

```bash
python scripts/run_engine.py --asof 2026-07-23T09:00                   # ranked list per team
python scripts/run_engine.py --asof 2026-07-23T09:00 --explain SYN-001  # one client in full
python -m unittest discover -s tests -v                                # 35 tests
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
