"""mindthegap: heat-risk prioritization rule engine (synthetic data, default weights, not calibrated)."""
from .config import ConfigError, load_config
from .data import DataError, load_clients, load_heat, load_hvi, parse_asof
from .scoring import ClientScore, rank_by_team, score_all, score_client

__all__ = [
    "ConfigError", "DataError", "ClientScore", "load_config", "load_clients", "load_heat",
    "load_hvi", "parse_asof", "rank_by_team", "score_all", "score_client",
]
