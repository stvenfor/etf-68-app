"""ETF momentum rotation (对齐小薪/次方风格全参数轮动)."""

from .config import DEFAULT_XIAOXIN_CONFIG, builtin_strategies, validate_config
from .service import (
    delete_strategy,
    fetch_public,
    list_strategies,
    run_rotation,
    save_strategy,
)

__all__ = [
    "DEFAULT_XIAOXIN_CONFIG",
    "builtin_strategies",
    "validate_config",
    "fetch_public",
    "list_strategies",
    "run_rotation",
    "save_strategy",
    "delete_strategy",
]
