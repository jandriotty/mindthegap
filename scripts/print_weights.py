"""Print the current factor weights as a Markdown table (straight from config/rules.toml).

Usage: python scripts/print_weights.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mindthegap import load_config  # noqa: E402


def main():
    cfg = load_config()
    print("| Factor | Tier | Group | OR used | Basis | Points |")
    print("|---|---|---|---|---|---|")
    for f in sorted(cfg.factors.values(), key=lambda f: (f.tier, -f.points, f.id)):
        print(f"| `{f.id}` | {f.tier} | {f.group or ''} | {f.or_ref:g} | {f.or_basis} | {f.points:.2f} |")


if __name__ == "__main__":
    main()
