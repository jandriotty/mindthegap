"""Run the rule engine without installing the package: python scripts/run_engine.py --asof ..."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mindthegap.cli import main  # noqa: E402

raise SystemExit(main())
