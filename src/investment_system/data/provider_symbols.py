"""Provider-specific symbol aliases while preserving internal asset identity."""
from pathlib import Path

from investment_system.core.config import load_yaml


def load_provider_symbols(path: str | Path = "config/provider_symbols.yaml") -> dict[str, dict[str, str]]:
    payload = load_yaml(path)
    providers = payload.get("providers", {})
    result: dict[str, dict[str, str]] = {}
    for provider, aliases in providers.items():
        if not isinstance(aliases, dict):
            raise ValueError(f"provider symbol aliases for {provider} must be a mapping")
        normalized = {str(internal).upper(): str(external).upper() for internal, external in aliases.items()}
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"duplicate internal symbols for {provider}")
        result[str(provider).lower()] = normalized
    return result


def provider_symbol(provider: str, internal_ticker: str, aliases: dict[str, dict[str, str]]) -> str:
    internal = internal_ticker.strip().upper()
    return aliases.get(provider.lower(), {}).get(internal, internal)

