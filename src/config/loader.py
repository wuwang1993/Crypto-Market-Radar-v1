"""YAML configuration loader.

Reads config files and resolves environment variable placeholders
in the form ``${VAR_NAME}``.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_ENV_VAR_RE = re.compile(r"\$\{(\w+)\}")


def _resolve_env(value: Any) -> Any:
    """Recursively resolve ${ENV_VAR} placeholders in a value."""
    if isinstance(value, str):
        def _replacer(match: re.Match[str]) -> str:
            var = match.group(1)
            resolved = os.environ.get(var, "")
            if not resolved:
                logger.warning("Environment variable %s is not set; using empty string", var)
            return resolved
        return _ENV_VAR_RE.sub(_replacer, value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    return value


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML config file, resolving environment variable placeholders.

    Args:
        path: Absolute or relative path to a ``.yaml`` file.

    Returns:
        Parsed configuration dictionary with all ``${VAR}`` values resolved.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    if raw is None:
        logger.warning("Config file %s is empty", path)
        return {}

    resolved = _resolve_env(raw)
    logger.info("Loaded config from %s (%d top-level keys)", path, len(resolved))
    return resolved
