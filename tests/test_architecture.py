"""The dependency rules of architecture §6, checked on the imports: the domain stands alone, the API reaches the
rest only through the use cases in `app`, the job queue knows only the storage and the feed only the analysis. The
MVP's flat modules join the rules as they move."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
ROOT = {"iplikci", "iplikci.__version__"}  # the package itself and its version: open to all

# package: the internal modules it may import (itself always)
RULES = {
    "iplikci.domain": (),
    # The service answers MCP beside the API, on the same app and the same analysis (ADR-0011).
    "iplikci.api": ("iplikci.app", "iplikci.mcp"),
    # MCP is the API's twin for Claude: the use cases in app, the domain's codes and labels. The tools the MVP had
    # still read a few of its flat modules; the stdio bridge reaches the service through the command line's client.
    "iplikci.mcp": (
        "iplikci.app",
        "iplikci.domain",
        "iplikci.analysis",
        "iplikci.categorize",
        "iplikci.insights",
        "iplikci.month_end",
        "iplikci.upcoming",
        "iplikci.service.client",
    ),
    "iplikci.jobs": ("iplikci.storage",),
    # The feed compares analyses and touches no storage; the analysis still lives in the MVP's flat modules. The
    # calendar and the forecast are pure too: what falls due soon, or goes below zero, is news.
    "iplikci.feed": (
        "iplikci.domain",
        "iplikci.analysis",
        "iplikci.insights",
        "iplikci.month_end",
        "iplikci.upcoming",
        "iplikci.forecast",
    ),
    # The days ahead are interpretation: the ledger and the insights only, no storage, files or network. A bill not
    # paid yet is told apart from its seller's regular payment as the ledger matches them (invoices).
    "iplikci.upcoming": ("iplikci.domain", "iplikci.analysis", "iplikci.insights", "iplikci.invoices"),
    "iplikci.forecast": ("iplikci.domain", "iplikci.analysis", "iplikci.insights", "iplikci.upcoming"),
    # Matching non-bank bills to the bank's rows is the ledger's own: the models only.
    "iplikci.invoices": ("iplikci.domain",),
    # The alert rules, the texts and the channels: no storage; the channels leave only through egress (ADR-0009).
    "iplikci.notify": ("iplikci.domain", "iplikci.egress"),
    # The exchange rates: the domain's codes and money; the providers leave only through egress (ADR-0009), and what
    # they fetch is stored by the use cases, not here.
    "iplikci.fx": ("iplikci.domain", "iplikci.egress", "iplikci.settings"),
    # What the banks' rates cost and what a foreign income is worth are interpretation, like the days ahead: the ledger,
    # the insights' months and valuation, and the rate book the dataset carries. It needs the book apart from the
    # providers, which is why it stands outside fx (that reaches the network); the use cases read the stored rates.
    "iplikci.exchange": ("iplikci.domain", "iplikci.analysis", "iplikci.insights", "iplikci.fx.book"),
    # Showing a document: the readers' own helpers in a process of its own; no storage, no vault, no network.
    "iplikci.viewer": ("iplikci.parsers",),
}


def _files(package: str) -> list[Path]:
    """A package's modules, or the module itself when it is a single file."""
    base = SRC / package.replace(".", "/")
    return sorted(base.rglob("*.py")) if base.is_dir() else [base.with_suffix(".py")]


def internal_imports(package: str) -> dict[str, set[str]]:
    """Every module of package, with the iplikci modules it imports (relative imports resolved)."""
    found: dict[str, set[str]] = {}
    for path in _files(package):
        parts = list(path.relative_to(SRC).with_suffix("").parts)
        current = parts[:-1]  # the package a relative import starts from
        if parts[-1] == "__init__":
            parts = parts[:-1]
        names: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    anchor = current[: len(current) - node.level + 1]
                    base = ".".join([*anchor, base] if base else anchor)
                names |= {base} if node.module else {f"{base}.{alias.name}" for alias in node.names}
        found[".".join(parts)] = {n for n in names if n == "iplikci" or n.startswith("iplikci.")}
    return found


@pytest.mark.parametrize("package", RULES)
def test_a_package_imports_only_what_the_architecture_allows(package):
    allowed = (package, *RULES[package])
    wrong = {
        module: sorted(n for n in names - ROOT if not any(n == a or n.startswith(f"{a}.") for a in allowed))
        for module, names in internal_imports(package).items()
    }
    assert {module: names for module, names in wrong.items() if names} == {}


# What opens a connection to another computer. Only egress may (ADR-0009); the command line's client talks to the
# service on 127.0.0.1 and nowhere else.
OPENERS = (
    "IMAP4_SSL(",
    "IMAP4(",
    "SMTP(",
    "SMTP_SSL(",
    "create_connection(",
    "urlopen(",
    "HTTPSConnection(",
    "HTTPConnection(",
    "build_opener(",
)
MAY_OPEN = {"iplikci/egress.py", "iplikci/service/client.py"}


def test_only_egress_opens_connections():
    found = {
        str(path.relative_to(SRC)): [o for o in OPENERS if o in path.read_text(encoding="utf-8")]
        for path in (SRC / "iplikci").rglob("*.py")
    }
    assert {name: openers for name, openers in found.items() if openers and name not in MAY_OPEN} == {}


def test_the_rule_check_sees_relative_imports():
    imports = internal_imports("iplikci.api")["iplikci.api.routes.auth"]
    assert {"iplikci.app", "iplikci.api.guard", "iplikci.api.context"} <= imports
    assert "iplikci.upcoming" in internal_imports("iplikci.forecast")["iplikci.forecast"]  # a module on its own
