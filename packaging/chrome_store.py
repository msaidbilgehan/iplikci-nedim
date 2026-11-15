"""The browser extension's new version to the Chrome Web Store (ADR-0022, K29), with the store's API v2 and a service
account, as the release workflow runs it:

    uv run python packaging/chrome_store.py extension/iplikci-kopru-0.9.0.zip

The store's item exists already: its first version is uploaded by hand from the developer dashboard, with its page,
its privacy policy and its visibility (public, ADR-0024). The command reads its settings from the environment:

- CWS_PUBLISHER_ID and CWS_ITEM_ID: the publisher's and the item's ids (the dashboard's Settings and Package pages);
- CWS_SERVICE_ACCOUNT_KEY: the JSON key of the service account the dashboard's Settings page names under "Service
  account".

It asks the store which version the item has published and has under way, and uploads only a newer one; the upload
is then sent for review, and the store publishes it once it passes (DEFAULT_PUBLISH). While an older version waits
for its review (or, staged, to be published) nothing is uploaded and the command fails, so the workflow's run says
so: once the review is over, re-running the store's job uploads the new one. With --deneme it says what it would do
and sends nothing.

This is a development tool for the workflow: it talks to Google's OAuth server and the Chrome Web Store only, never
from the installed program."""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from iplikci.versions import newer

TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/chromewebstore"
API = "https://chromewebstore.googleapis.com"
UPLOAD = "https://chromewebstore.googleapis.com/upload"
POLL_SECONDS = 5.0
POLL_TIMES = 60
# A submitted revision in these states still counts: a new upload must be newer than it. A rejected or cancelled one
# no longer does.
UNDER_WAY = frozenset({"PENDING_REVIEW", "STAGED", "PUBLISHED_TO_TESTERS"})
# The store takes no new package while a submission waits for its review or, staged, to be published.
WAITING = frozenset({"PENDING_REVIEW", "STAGED"})

type Send = Callable[[urllib.request.Request], tuple[int, bytes]]


class StoreError(Exception):
    """The store refused or the settings are missing; the message says what (Turkish)."""


@dataclass(frozen=True, slots=True)
class Settings:
    publisher: str
    item: str
    account: Mapping[str, Any]  # the service account's JSON key

    @property
    def name(self) -> str:
        return f"publishers/{self.publisher}/items/{self.item}"


def settings_from(environ: Mapping[str, str]) -> Settings:
    publisher, item = environ.get("CWS_PUBLISHER_ID", "").strip(), environ.get("CWS_ITEM_ID", "").strip()
    key = environ.get("CWS_SERVICE_ACCOUNT_KEY", "").strip()
    missing = [name for name, value in (("CWS_PUBLISHER_ID", publisher), ("CWS_ITEM_ID", item)) if not value]
    if not key:
        missing.append("CWS_SERVICE_ACCOUNT_KEY")
    if missing:
        raise StoreError(f"mağaza ayarları eksik: {', '.join(missing)}")
    try:
        account: object = json.loads(key)
    except ValueError:
        raise StoreError("CWS_SERVICE_ACCOUNT_KEY bir JSON anahtar dosyası değil") from None
    if not isinstance(account, dict) or not {"client_email", "private_key"} <= set(cast(dict[str, Any], account)):
        raise StoreError("CWS_SERVICE_ACCOUNT_KEY bir servis hesabının anahtarı değil (client_email, private_key yok)")
    return Settings(publisher, item, cast(dict[str, Any], account))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def assertion(account: Mapping[str, Any], now: float) -> str:
    """The signed JWT a service account trades for an access token (RS256, an hour at most)."""
    header = {"alg": "RS256", "typ": "JWT"}
    if account.get("private_key_id"):
        header["kid"] = str(account["private_key_id"])
    claims = {
        "iss": str(account["client_email"]),
        "scope": SCOPE,
        "aud": TOKEN_URL,
        "iat": int(now),
        "exp": int(now) + 3600,
    }
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
    key = serialization.load_pem_private_key(str(account["private_key"]).encode(), password=None)
    if not isinstance(key, RSAPrivateKey):
        raise StoreError("servis hesabının anahtarı bir RSA anahtarı değil")
    signature = key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input}.{_b64(signature)}"


def zip_version(path: Path) -> str:
    """The version the package's manifest says."""
    with zipfile.ZipFile(path) as archive:
        found: object = json.loads(archive.read("manifest.json"))
    if not isinstance(found, dict) or not isinstance(cast(dict[str, Any], found).get("version"), str):
        raise StoreError(f"{path.name} içinde sürümü olan bir manifest.json yok")
    return str(cast(dict[str, Any], found)["version"])


def _revision(status: Mapping[str, Any], part: str) -> tuple[str, list[str]] | None:
    """A revision's state and versions from fetchStatus's answer."""
    revision = status.get(part)
    if not isinstance(revision, dict):
        return None
    found = cast(dict[str, Any], revision)
    versions = [
        str(cast(dict[str, Any], channel)["crxVersion"])
        for channel in found.get("distributionChannels") or []
        if isinstance(channel, dict) and isinstance(cast(dict[str, Any], channel).get("crxVersion"), str)
    ]
    return str(found.get("state", "")), versions


def store_versions(status: Mapping[str, Any]) -> list[str]:
    """The versions a new upload must be newer than: the published one and a submitted one still under way."""
    found: list[str] = []
    published = _revision(status, "publishedItemRevisionStatus")
    if published:
        found += published[1]
    submitted = _revision(status, "submittedItemRevisionStatus")
    if submitted and submitted[0] in UNDER_WAY:
        found += submitted[1]
    return found


def waiting(status: Mapping[str, Any]) -> str:
    """The submitted version still waiting for its review or to be published, with its state; else empty."""
    submitted = _revision(status, "submittedItemRevisionStatus")
    if not submitted or submitted[0] not in WAITING:
        return ""
    return f"{', '.join(submitted[1]) or '?'} ({submitted[0]})"


def send(request: urllib.request.Request) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(request, timeout=120) as answer:
            return int(answer.status), answer.read()
    except urllib.error.HTTPError as exc:
        with exc:
            return int(exc.code), exc.read()


class Store:
    def __init__(self, settings: Settings, send_with: Send = send, clock: Callable[[], float] = time.time) -> None:
        self.settings = settings
        self._send = send_with
        self._clock = clock
        self._token = ""

    def token(self) -> str:
        if not self._token:
            form = urllib.parse.urlencode(
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion(self.settings.account, self._clock()),
                }
            ).encode()
            found = self._json(urllib.request.Request(TOKEN_URL, data=form, method="POST"), "erişim belirteci")
            self._token = str(found.get("access_token", ""))
            if not self._token:
                raise StoreError("Google erişim belirteci vermedi")
        return self._token

    def status(self) -> dict[str, Any]:
        return self._call("GET", f"{API}/v2/{self.settings.name}:fetchStatus", None, "durum")

    def upload(self, package: bytes) -> dict[str, Any]:
        return self._call("POST", f"{UPLOAD}/v2/{self.settings.name}:upload", package, "yükleme")

    def publish(self) -> dict[str, Any]:
        body = json.dumps({"publishType": "DEFAULT_PUBLISH"}).encode()
        return self._call("POST", f"{API}/v2/{self.settings.name}:publish", body, "yayın", "application/json")

    def _call(
        self, method: str, url: str, body: bytes | None, what: str, content_type: str = "application/octet-stream"
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token()}"}
        if body is not None:
            headers["Content-Type"] = content_type
        return self._json(urllib.request.Request(url, data=body, headers=headers, method=method), what)

    def _json(self, request: urllib.request.Request, what: str) -> dict[str, Any]:
        status, raw = self._send(request)
        try:
            found: object = json.loads(raw or b"{}")
        except ValueError:
            found = {}
        if status >= 300 or not isinstance(found, dict):
            detail = raw.decode("utf-8", errors="replace")[:500]
            raise StoreError(f"mağaza {what} isteğini {status} ile reddetti: {detail}")
        return cast(dict[str, Any], found)


def release(store: Store, package: Path, dry_run: bool = False, sleep: Callable[[float], None] = time.sleep) -> str:
    """Upload the package when its version is newer than what the store has, and send it for review; what was done."""
    version = zip_version(package)
    status = store.status()
    known = store_versions(status)
    if any(not newer(version, other) for other in known):
        return f"{version} mağazadakinden ({', '.join(known)}) yeni değil; yüklenmedi"
    held = waiting(status)
    if held:
        raise StoreError(
            f"mağazada {held} bekliyor; {version} yüklenmedi. İnceleme bitince iş akışının mağaza işini yeniden "
            "çalıştırın"
        )
    if dry_run:
        return f"{version} yüklenecekti (mağazada: {', '.join(known) or 'yok'})"
    uploaded = store.upload(package.read_bytes())
    state = str(uploaded.get("uploadState", ""))
    for _ in range(POLL_TIMES):
        if state != "IN_PROGRESS":
            break
        sleep(POLL_SECONDS)
        state = str(store.status().get("lastAsyncUploadState", ""))
    if state != "SUCCEEDED":
        raise StoreError(f"{version} yüklenemedi ({state or 'yanıt yok'}): {json.dumps(uploaded)[:500]}")
    published = store.publish()
    return f"{version} yüklendi ve incelemeye gönderildi ({published.get('state', '?')})"


def main() -> None:
    parser = argparse.ArgumentParser(description="Eklentinin yeni sürümünü Chrome Web Store'a yükler (ADR-0022).")
    parser.add_argument("paket", type=Path, help="eklentinin mağaza paketi (iplikci-kopru-<sürüm>.zip)")
    parser.add_argument("--deneme", action="store_true", help="yalnızca ne yapılacağını söyle, hiçbir şey gönderme")
    args = parser.parse_args()
    try:
        print(release(Store(settings_from(os.environ)), args.paket, args.deneme))
    except StoreError as exc:
        sys.exit(f"Mağazaya yüklenemedi: {exc}")


if __name__ == "__main__":
    main()
