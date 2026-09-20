# data

| Folder | What | Read |
|---|---|---|
| `synthetic/clients/` | 10 fictional social-worker-style client records with per-field source and date | `synthetic/clients/README.md` |
| `synthetic/heat_events/` | A synthetic NYC heat wave, Mon 2026-07-20 to Sun 2026-07-26 | `synthetic/heat_events/README.md` |

The two datasets share a date (client `extract_date` = first day of the heat week) and join on `borough`.

## Rules
- **Everything committed here is synthetic.** IDs are `SYN-###`, and ZIP codes are only geography. Nothing was derived from real patient records.
- **Don't commit anything that shouldn't be public.** Put it in `data/private/`, which is git-ignored. That includes the official hackathon dataset until its sharing terms are confirmed.
- **Regenerate, don't hand-edit.** Change the generator script, re-run it, and commit both.
