# Heat Check-In

**Health in Climate AI Hackathon, NYC 2026** — *Reaching high-risk New Yorkers before climate emergencies*

Heat Check-In turns a heat advisory into an explained outreach list for behavioral health care teams serving people with serious mental illness or substance use disorders. It combines a transparent rule engine, AI-generated call scripts, and a workflow designed around the care navigator's next action.

**All data in this repo is synthetic. No real patient data. Default weights are NOT calibrated.**

## Team — Mind the Gap

| Member   | Contribution                                      |
|----------|---------------------------------------------------|
| Ellen    | Synthetic client data, heat events, rule engine    |
| Jill     | LLM call-card generation, integration              |
| Hyejin   | Frontend design, UX flow, landing page             |
| Giovanna | Clinical research, factor evidence                 |
| Seren    | Hazard trigger research                            |

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env        # add your Anthropic API key (optional — template mode works without it)
python app/server.py         # starts on http://localhost:5001
```

The server loads the rule engine, scores all clients, and serves the frontend.

### Options

```bash
python app/server.py --asof 2026-07-23T09:00   # default: peak heat day (extreme heat warning)
python app/server.py --asof 2026-07-22T14:00   # day before peak (heat advisory)
python app/server.py --asof 2026-07-26T09:00   # quiet day (no hazard)
python app/server.py --port 8080               # different port
```

## How it works

### 1. Rule engine (Python)

A transparent, hand-weighted **additive points scorecard** — not ML, not a decision tree — that evaluates 17 risk factors per client:

- **Tier 1** (strongest evidence): cooling status, unsheltered housing, outdoor exposure, antipsychotic/anticholinergic medications, psychotic-spectrum diagnosis, mobility, daily home-leaving
- **Tier 2**: mood disorder, other heat-sensitive medications, active substance use, cardiometabolic conditions, age, living alone
- **Tier 3**: neighborhood HVI, energy insecurity, ED utilization pattern, service recency gap

Each factor evaluates to **present / absent / unknown / n/a**. Unknown factors produce a **range** (low = 0, high = full points, expected = prior-weighted estimate), never a false assumption of safety.

**Priority = vulnerability × hazard multiplier**. Clients are banded as urgent / high / moderate / low. **Confidence** (data quality × hazard trust) is reported separately from risk.

Details: [docs/rule-engine.md](docs/rule-engine.md)

### 2. Call-card generation (Python + Claude)

Given a scored client, generates a personalized call script:
- Greeting appropriate to the person's situation
- 5-6 check-in questions that skip confirmed facts and focus on the engine's highest-impact unknowns
- Closing with heat-safety reminders and NYC resources

**LLM mode** (with `ANTHROPIC_API_KEY`): sends the full scoring context to Claude for richer, context-aware scripts.
**Template mode** (no key): deterministic rule-based generation using the engine's unknowns and factor results.

### 3. Frontend (HTML/CSS/JS)

- **Landing page**: explains the product, workflow, and principles
- **Call sheet**: scored and ranked client list with band filters, confidence indicators, and team grouping
- **Client detail**: full factor breakdown, evidence, blind spots, and interactive call-card generation

No framework — vanilla HTML served by Flask. No patient data stored.

## Layout

```
mindthegap/
├── app/server.py             Flask API (engine + call cards + static files)
├── static/                   Frontend (HTML/CSS/JS)
├── src/mindthegap/           Rule engine
│   ├── config.py             Load and validate config
│   ├── data.py               Load clients, heat events, HVI
│   ├── factors.py            17 factor evaluators
│   ├── hazard.py             Heat hazard timeline
│   ├── scoring.py            Combine into scores with confidence
│   ├── callcard.py           LLM/template call-card generation
│   └── cli.py                CLI interface
├── config/                   Engine settings (weights, bands, ICD map, drugs)
├── data/
│   ├── synthetic/clients/    10 synthetic client records (JSON + CSV)
│   ├── synthetic/heat_events/ 7-day NYC heat wave (hourly, daily, alerts, forecasts)
│   └── reference/            NYC HVI by ZIP (subset)
├── scripts/                  CLI runner, weight printer, HVI fetcher
├── tests/test_engine.py      35 engine tests
└── docs/rule-engine.md       Scoring algorithm documentation
```

## API

| Endpoint                     | Method | Description                           |
|------------------------------|--------|---------------------------------------|
| `/api/scores`                | GET    | All scored clients (optional `?team=`) |
| `/api/callcard/<client_id>`  | POST   | Generate a call card for one client    |
| `/api/hazard`                | GET    | Current hazard timeline                |

## CLI (rule engine only)

```bash
python scripts/run_engine.py --asof 2026-07-23T09:00                    # ranked list per team
python scripts/run_engine.py --asof 2026-07-23T09:00 --explain SYN-001   # one client in full
python -m unittest discover -s tests -v                                  # 35 tests
```

## Regenerate synthetic data

```bash
python data/synthetic/clients/generate_synthetic_clients.py
python data/synthetic/heat_events/generate_heat_events.py
```

Both scripts are deterministic and run their own consistency checks.

## Data sources

| Source | Type | Use |
|--------|------|-----|
| NYC HVI by ZCTA (NYC Open Data) | Real public data | Neighborhood-level heat vulnerability context |
| CDC Heat-Sensitive Medication Guidance | Real reference | Drug-class mapping for medication factors |
| Bouchama 2007 meta-analysis, Semenza 1996 NEJM | Published studies | Odds ratios for factor weights |
| NPCC4 Climate Projections | Real projections | Future heat-day estimates |
| NWS heat products | Real alert criteria | Hazard level and product assignment |
| Synthetic clients (10 records) | Synthetic | Engine testing and demo |
| Synthetic heat events (7 days) | Synthetic | Engine testing and demo |
