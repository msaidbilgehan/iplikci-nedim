"""Secrets in the system keyring (architecture §20): macOS Keychain, Windows Credential Manager, the Secret
Service on Linux. Where a system has no keyring (a Linux server), each secret is read from its environment
variable instead. A secret is never written to a file, an argument or a log.
"""

import os
from dataclasses import dataclass
from types import ModuleType

SERVICE = "iplikci"


class SecretError(Exception):
    """The keyring could not be used; the message says why and what to do (Turkish)."""


@dataclass(frozen=True, slots=True)
class Secret:
    account: str  # the user name of the keyring entry under SERVICE
    env: str  # the environment variable that stands in where there is no keyring


def mail(address: str) -> Secret:
    """The e-mail app password, for the IMAP connector only."""
    return Secret(f"mail:{address}", "IPLIKCI_MAIL_PASSWORD")


TELEGRAM_BOT = Secret("telegram-bot", "IPLIKCI_TELEGRAM_TOKEN")
API_TOKEN = Secret("api-token", "IPLIKCI_API_TOKEN")
EVDS = Secret("evds", "IPLIKCI_EVDS_KEY")


def _keyring() -> ModuleType:
    import keyring  # imported on use: it picks a backend when imported

    return keyring


def load(secret: Secret) -> str | None:
    """The secret from its environment variable, else from the keyring; None when it is in neither."""
    value = os.environ.get(secret.env)
    if value:
        return value
    keyring = _keyring()
    try:
        found: str | None = keyring.get_password(SERVICE, secret.account)
    except keyring.errors.NoKeyringError:
        return None
    except keyring.errors.KeyringError as exc:
        raise SecretError(
            f"anahtar zinciri okunamadı ({exc}); anahtar zinciri olmayan sistemlerde {secret.env} ortam "
            "değişkenini kullanın"
        ) from exc
    return found or None


def store(secret: Secret, value: str) -> bool:
    """Keep the secret in the keyring; False when the system has none (then its environment variable is the
    way)."""
    keyring = _keyring()
    try:
        keyring.set_password(SERVICE, secret.account, value)
    except keyring.errors.NoKeyringError:
        return False
    except keyring.errors.KeyringError as exc:
        raise SecretError(f"anahtar zincirine yazılamadı: {exc}") from exc
    return True


def delete(secret: Secret) -> None:
    """Forget the secret; nothing happens when there was none."""
    keyring = _keyring()
    try:
        keyring.delete_password(SERVICE, secret.account)
    except keyring.errors.KeyringError:  # PasswordDeleteError when there was none, NoKeyringError without one
        pass
