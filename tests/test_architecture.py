"""The dependency rules of architecture §6, checked on the imports: the domain stands alone, and the API reaches
the rest only through the use cases in `app`. The MVP's flat modules join the rules as they move."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
ROOT = {"iplikci", "iplikci.__version__"}  # the package itself and its version: open to all

# package: the internal modules it may import (itself always)
RULES = {
    "iplikci.domain": (),
    "iplikci.api": ("iplikci.app",),
}


def internal_imports(package: str) -> dict[str, set[str]]:
    """Every module of package, with the iplikci modules it imports (relative imports resolved)."""
    found: dict[str, set[str]] = {}
    for path in (SRC / package.replace(".", "/")).rglob("*.py"):
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


def test_the_rule_check_sees_relative_imports():
    imports = internal_imports("iplikci.api")["iplikci.api.routes.auth"]
    assert {"iplikci.app", "iplikci.api.guard", "iplikci.api.context"} <= imports
