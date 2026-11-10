"""The keys a release's manifest may be signed with (ADR-0022), by their names: Ed25519 public keys, raw and in base64.
The private key lives only in the release workflow's secret (UPDATE_SIGNING_KEY) and its owner's keychain. A new key
is added here in a release signed with the old one, and the old one leaves after the last release it signed."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

TRUSTED: Final[Mapping[str, str]] = MappingProxyType(
    {
        "2026-11": "MXKV5fzx9bHC3PY1EdipdAwK9BIgCcwm5ou+X8s4O5w=",
    }
)
