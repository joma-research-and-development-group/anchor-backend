import hashlib
import json
from typing import Any


def _semver_tuple(v: str) -> tuple[int, ...]:
    """Parse semver string to comparable tuple."""
    parts = v.replace("-", ".").split(".")
    result = []
    for p in parts[:3]:
        try:
            result.append(int(p))
        except ValueError:
            result.append(0)
    while len(result) < 3:
        result.append(0)
    return tuple(result)


def _matches_conditions(conditions: dict[str, Any], context: dict[str, Any]) -> bool:
    """Check if client context matches override conditions."""
    client_version = context.get("app_version", "0.0.0")
    client_platform = context.get("platform", "")
    client_country = context.get("country", "")

    if "min_version" in conditions:
        if _semver_tuple(client_version) < _semver_tuple(conditions["min_version"]):
            return False
    if "max_version" in conditions:
        if _semver_tuple(client_version) > _semver_tuple(conditions["max_version"]):
            return False
    if "platform" in conditions:
        platforms = conditions["platform"]
        if isinstance(platforms, list) and client_platform not in platforms:
            return False
    if "country" in conditions:
        countries = conditions["country"]
        if isinstance(countries, list) and client_country not in countries:
            return False
    return True


def evaluate_config(entries_with_overrides: list[dict[str, Any]], client_context: dict[str, Any]) -> dict[str, Any]:
    """Evaluate config entries with overrides, returning key→value dict."""
    result: dict[str, Any] = {}
    for entry in entries_with_overrides:
        key = entry["key"]
        value = entry["default_value"]
        overrides = sorted(entry.get("overrides", []), key=lambda o: o.get("priority", 0), reverse=True)
        for override in overrides:
            if _matches_conditions(override.get("conditions", {}), client_context):
                value = override["value"]
                break
        result[key] = value
    return result


def compute_etag(config_dict: dict[str, Any]) -> str:
    """Compute ETag from config dictionary."""
    serialized = json.dumps(config_dict, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()
