"""Where the releases are (ADR-0022): a GitHub repository whose releases can be read without an account. The release
workflow puts each version there with its signed manifest under a fixed name, so the latest one is always at the
same address."""

import urllib.parse

REPO = "msaidbilgehan/iplikci-nedim"  # the owner and the repository, as in github.com/<owner>/<repository>
MANIFEST = "iplikci-nedim-surum.json"
SIGNATURE = f"{MANIFEST}.sig"


def latest(name: str, repo: str = REPO) -> str:
    """The path on github.com of a file of the latest release; GitHub redirects it to the release's own."""
    return f"/{repo}/releases/latest/download/{urllib.parse.quote(name)}"


def tagged(tag: str, name: str, repo: str = REPO) -> str:
    """The path on github.com of a file of the release with this tag."""
    return f"/{repo}/releases/download/{urllib.parse.quote(tag)}/{urllib.parse.quote(name)}"


def page(tag: str = "", repo: str = REPO) -> str:
    """The release's page for the user, or the releases' page without a tag: where the installers are."""
    if tag:
        return f"https://github.com/{repo}/releases/tag/{urllib.parse.quote(tag)}"
    return f"https://github.com/{repo}/releases/latest"
