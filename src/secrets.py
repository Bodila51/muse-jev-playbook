from __future__ import annotations

import os


TYPESAFE_API_KEY_ENV = "TYPESAFE_API_KEY"


class CredentialError(RuntimeError):
    """A configured provider credential is missing or blank."""


def require_credential(env_name: str) -> str:
    """Return one nonblank credential from the explicitly named environment variable."""
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise CredentialError(f"{env_name} is missing or blank")
    return value


def ensure_typesafe_api_key() -> str:
    """Require the Developer track's official TypeSafe credential."""
    return require_credential(TYPESAFE_API_KEY_ENV)
