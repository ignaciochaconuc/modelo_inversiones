"""Explicit CLI environment bootstrap; importing this module never reads secrets."""
from pathlib import Path
from collections.abc import Callable
from functools import wraps
import json
import os

from dotenv import load_dotenv


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class EnvironmentBootstrapError(RuntimeError):
    """Safe fixed error codes only, without dotenv contents or exception chaining."""


def redact_external_credentials(text: str) -> str:
    """Redact process API keys without reading .env or exposing credential values."""
    for name, value in os.environ.items():
        if name.endswith("API_KEY") and value:
            for representation in (value, json.dumps(value, ensure_ascii=True)[1:-1]):
                text = text.replace(representation, "[REDACTED]")
    return text


def safe_cli_errors(main: Callable[[], int]) -> Callable[[], int]:
    """Suppress unsafe third-party exception bodies at external CLI boundaries."""
    @wraps(main)
    def wrapped() -> int:
        try:
            return main()
        except EnvironmentBootstrapError as error:
            code = ("explicit_real_operation_authorization_required"
                    if str(error) == "explicit_real_operation_authorization_required"
                    else "repository_environment_load_failed")
        except Exception:
            code = "cli_operation_failed"
        print(json.dumps({"status": "blocked", "error": code}))
        return 2
    return wrapped


def load_repository_environment(*, real_operation_authorized: bool) -> bool:
    """Load only the repository's .env after explicit real-operation permission.

    Existing process variables, including empty values, take precedence.
    No cwd search, alternate path argument, credential return or value logging.
    Missing .env is allowed: callers may use system-provided credentials.
    """
    if real_operation_authorized is not True:
        raise EnvironmentBootstrapError("explicit_real_operation_authorization_required")
    failed = False
    loaded = False
    try:
        root = REPOSITORY_ROOT.resolve()
        path = root / ".env"
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("unsafe dotenv path")
        loaded = load_dotenv(dotenv_path=path, override=False, verbose=False,
                             interpolate=False, encoding="utf-8")
    except Exception:
        # Raise OUTSIDE the handler: not even __context__ contains file contents.
        failed = True
    if failed:
        raise EnvironmentBootstrapError("repository_environment_load_failed")
    return loaded
