"""Edit the user's rule file (rules/personal.yaml) as text, so the user's comments and layout survive.

A few narrow edits are automated: a named merchant rule under a category, an entry in `_biten`, an income that comes
every month (`_düzenli_gelir`), a merchant's own necessity (`_gereklilik_işyeri`) and the commitment categories
(`_düzenli`). Anything else is a whole new text the
caller writes. Every change is validated by building the categorizer from it,
over the rules shipped with the app, before the file is replaced; the previous file goes to the history.
"""

import difflib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yaml

from .categorize import DEFAULT_RULES, Categorizer, RuleSet
from .domain.text import fold

_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
# A mapping key at the start of a line: quoted, or plain up to the first ": ".
_KEY = re.compile(r"""^(?P<key>"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^\s#'"\[\]{}\-][^#]*?)\s*:(?=\s|$)""")
_GENERIC_KEYS = {"_", "_ZAYIF"}


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _key(line: str) -> str | None:
    """The key a line of the file starts, or None for comments, list items and continued lists."""
    m = _KEY.match(line.strip())
    if not m:
        return None
    raw = m["key"]
    if raw[0] in "\"'":
        try:
            return str(yaml.safe_load(raw))
        except yaml.YAMLError:
            return None
    return raw.strip()


def _is_content(line: str) -> bool:
    return bool(line.strip()) and not line.lstrip().startswith("#")


def _block_end(lines: list[str], start: int) -> int:
    """Index just after the last line nested under lines[start] (blank lines after it excluded)."""
    level, last = _indent(lines[start]), start + 1
    for j in range(start + 1, len(lines)):
        if not lines[j].strip():
            continue
        if _indent(lines[j]) <= level:
            break
        last = j + 1
    return last


def _scalar(value: str, key: bool = False) -> str:
    """value as YAML: plain when it reads back unchanged (the file's style), otherwise double-quoted."""
    if value and value == value.strip() and not value.startswith("re:"):
        text = f"{value}: x" if key else f"[{value}]"
        try:
            if yaml.safe_load(text) == ({value: "x"} if key else [value]):
                return value
        except yaml.YAMLError:
            pass
    return json.dumps(value, ensure_ascii=False)


def _trailing_comment(stripped: str, value) -> str:
    """The "  # …" a line ends with ("#" can also sit inside a quoted regex, so check by reparsing)."""
    for m in re.finditer(r"\s+#", stripped):
        try:
            if yaml.safe_load(stripped[: m.start()]) == value:
                return stripped[m.start() :]
        except yaml.YAMLError:
            continue
    return ""


def _lines(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines


def _find_category(lines: list[str], category: str) -> int | None:
    group, found = None, []
    for i, line in enumerate(lines):
        if not _is_content(line):
            continue
        key = _key(line)
        if _indent(line) == 0:
            group = key
        elif _indent(line) == 2 and key and group and not group.startswith("_") and fold(key) == fold(category):
            found.append(i)
    if len(found) > 1:
        raise ValueError(f"'{category}' birden çok grupta var; dosyayı write_rules ile düzenleyin")
    return found[0] if found else None


def _add_category(lines: list[str], category: str, group: str) -> list[str]:
    """An empty category under its group, the group made when the file has none yet (at the end: the order of
    the groups, and so their colours, comes from the rules shipped with the app)."""
    entry = f"  {_scalar(category, key=True)}:\n"
    for i, line in enumerate(lines):
        if _is_content(line) and _indent(line) == 0 and fold(_key(line) or "") == fold(group):
            if re.match(r"^[^#]*:\s*\{\}", line):
                lines[i] = re.sub(r":\s*\{\}", ":", line, count=1)
            end = _block_end(lines, i)
            return [*lines[:end], entry, *lines[end:]]
    gap = ["\n"] if lines and lines[-1].strip() else []
    return [*lines, *gap, f"{_scalar(group, key=True)}:\n", entry]


def add_merchant_rule(
    text: str, category: str, merchant: str, patterns: list[str], homes: Mapping[str, str] | None = None
) -> str:
    """Add a named merchant (or more patterns for one) to a category. Named rules are tried before every keyword,
    in file order. homes (category -> group, e.g. the categorizer's categories) lets the rule go to a category the
    file does not have yet: one of the rules shipped with the app."""
    patterns = [p.strip() for p in patterns if p.strip()]
    if not merchant.strip() or not patterns:
        raise ValueError("işyeri adı ve en az bir desen gerekli")
    merchant = merchant.strip()
    lines = _lines(text)
    start = _find_category(lines, category)
    if start is None:
        home = next(((c, g) for c, g in (homes or {}).items() if fold(c) == fold(category)), None)
        if home is None:
            raise ValueError(f"'{category}' adlı kategori yok; var olan kategoriler için read_rules")
        lines = _add_category(lines, *home)
        start = _find_category(lines, home[0])
        assert start is not None
    if re.match(r"^\s*[^#]*:\s*\{\}", lines[start]):  # "Diğer Harcamalar: {}": the block is empty so far
        lines[start] = re.sub(r":\s*\{\}", ":", lines[start], count=1)
    end = _block_end(lines, start)
    insert = end
    for j in range(start + 1, end):
        if not _is_content(lines[j]) or _indent(lines[j]) != 4:
            continue
        key = _key(lines[j])
        if key is None:
            continue
        if fold(key) == fold(merchant):  # known merchant: more patterns
            try:
                current = yaml.safe_load(lines[j].strip())
            except yaml.YAMLError:
                current = None
            known = current.get(key) if isinstance(current, dict) else None
            if isinstance(known, str):
                known = [known]
            if not isinstance(known, list):
                raise ValueError(f"'{key}' satırı birden çok satıra yayılmış; write_rules ile düzenleyin")
            merged = known + [p for p in patterns if fold(p) not in {fold(str(k)) for k in known}]
            comment = _trailing_comment(lines[j].strip(), current)
            lines[j] = " " * 4 + f"{_scalar(key, key=True)}: [{', '.join(_scalar(str(p)) for p in merged)}]{comment}\n"
            return "".join(lines)
        if fold(key) in _GENERIC_KEYS and insert == end:
            insert = j  # named merchants go above the generic keywords, as in the rest of the file
    line = " " * 4 + f"{_scalar(merchant, key=True)}: [{', '.join(_scalar(p) for p in patterns)}]\n"
    lines.insert(insert, line)
    return "".join(lines)


def add_ended(text: str, merchant: str, month: str, note: str = "") -> str:
    """List a payment or habit as ended in `_biten`: no payment is expected after month (YYYY-MM)."""
    if not _MONTH.fullmatch(month):
        raise ValueError("ay YYYY-AA biçiminde olmalı (ör. 2026-10)")
    lines = _lines(text)
    note = " ".join(note.split())
    entry = f"  {_scalar(merchant, key=True)}: {month}" + (f"  # {note}" if note else "") + "\n"
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if _is_content(line) and _indent(line) == 0 and fold(_key(line) or "") == "_BITEN"
        ),
        None,
    )
    if start is None:
        return "".join(lines) + (
            "\n# Bittiğini ya da iptal ettiğinizi bildiğiniz ödemeler: işyeri adı ve son ödemenin "
            "yapıldığı ay (YYYY-AA).\n_biten:\n" + entry
        )
    if re.match(r"^[^#]*:\s*\{\}", lines[start]):
        lines[start] = re.sub(r":\s*\{\}", ":", lines[start], count=1)
    end = _block_end(lines, start)
    for j in range(start + 1, end):
        key = _key(lines[j]) if _is_content(lines[j]) else None
        if key is not None and fold(key) == fold(merchant):
            old_note = re.search(r"\s+#.*$", lines[j].rstrip("\n"))
            lines[j] = entry if note or not old_note else f"  {_scalar(key, key=True)}: {month}{old_note[0]}\n"
            return "".join(lines)
    lines.insert(end, entry)
    return "".join(lines)


def _number(value: Decimal) -> str:
    """An amount as the rule file writes it: plain digits, a point before the decimals ("1800", "1250.5")."""
    text = format(value.normalize(), "f")
    return text if "." not in text else text.rstrip("0").rstrip(".")


def add_income(text: str, merchant: str, amount: Decimal, currency: str, day: int) -> str:
    """List an income in `_düzenli_gelir`: it comes every month, amount in its currency (TL or a code such as EUR),
    on day of the month. An entry the payer already has is replaced; its comment stays."""
    if amount <= 0 or not amount.is_finite():
        raise ValueError("tutar sıfırdan büyük olmalı")
    if not 1 <= day <= 31:
        raise ValueError("gün 1 ile 31 arasında olmalı")
    money = "TL" if currency in ("TL", "TRY") else currency
    value = f"{{tutar: {_number(amount)}, para: {money}, gün: {day}}}"
    lines = _lines(text)
    start = _top(lines, "_DUZENLI_GELIR")
    if start is None:
        gap = "\n" if lines and lines[-1].strip() else ""
        return "".join(lines) + (
            f"{gap}# Her ay geldiğini bildiğiniz gelirler: ödeyenin işlemlerdeki adı, aylık tutarı, para birimi ve "
            "geldiği gün.\n_düzenli_gelir:\n" + f"  {_scalar(merchant, key=True)}: {value}\n"
        )
    if re.match(r"^[^#]*:\s*\{\}", lines[start]):
        lines[start] = re.sub(r":\s*\{\}", ":", lines[start], count=1)
    end = _block_end(lines, start)
    for j in range(start + 1, end):
        key = _key(lines[j]) if _is_content(lines[j]) else None
        if key is not None and fold(key) == fold(merchant):
            comment = re.search(r"\s+#[^}]*$", lines[j].rstrip("\n"))
            lines[j] = f"  {_scalar(key, key=True)}: {value}{comment[0] if comment else ''}\n"
            return "".join(lines)
    lines.insert(end, f"  {_scalar(merchant, key=True)}: {value}\n")
    return "".join(lines)


def remove_income(text: str, merchant: str) -> str:
    """Take an income off `_düzenli_gelir`: it counts again only once its documents make it a series."""
    lines = _lines(text)
    start = _top(lines, "_DUZENLI_GELIR")
    if start is None or not _drop_entry(lines, start, merchant):
        raise ValueError(f"'{merchant}' kişisel kurallarda her ay gelen bir gelir olarak yazılı değil")
    return "".join(lines)


def validate(text: str, name: str = "personal.yaml", defaults: Path | None = DEFAULT_RULES) -> None:
    """Raise ValueError (with the reason, in Turkish) unless the text is a rule file the program reads over the
    rules below it (defaults)."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML okunamadı: {exc}") from exc
    if data is not None and not isinstance(data, dict):
        raise ValueError(f"{name} 'Ana grup: …' eşlemelerinden oluşmalı")
    try:
        Categorizer.from_layers(RuleSet.parse(text, name), *([RuleSet.read(defaults)] if defaults else []))
    except Exception as exc:  # any failure here means the program could not read these rules
        raise ValueError(f"kurallar okunamadı: {type(exc).__name__}: {exc}") from exc


def replace(path: Path, text: str, history: Path) -> Path | None:
    """Write the new rules atomically, the previous file kept in history; returns that copy (None for a first
    file)."""
    backup = None
    if path.exists():
        history.mkdir(parents=True, exist_ok=True)
        backup = _free(history / f"{path.stem} {datetime.now():%Y-%m-%d %H.%M.%S}{path.suffix}")
        backup.write_bytes(path.read_bytes())
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, tmp = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=path.suffix, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return backup


def _free(path: Path) -> Path:
    """path, or 'name (2).ext' and so on if it exists: a history copy never replaces another."""
    candidate, n = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return candidate


def diff(old: str, new: str, name: str, limit: int = 80) -> str:
    lines = list(
        difflib.unified_diff(old.splitlines(), new.splitlines(), f"{name} (önce)", f"{name} (sonra)", lineterm="", n=1)
    )
    if len(lines) > limit:
        lines = lines[:limit] + [f"… {len(lines) - limit} satır daha"]
    return "\n".join(lines)


def _top(lines: list[str], folded: str) -> int | None:
    """The line a top-level key starts (`_biten:`, `_düzenli:`), by its folded name."""
    return next(
        (
            i
            for i, line in enumerate(lines)
            if _is_content(line) and _indent(line) == 0 and fold(_key(line) or "") == folded
        ),
        None,
    )


def _drop_entry(lines: list[str], start: int, key: str) -> bool:
    """Remove the one-line `key: value` entry under the block at start; whether there was one."""
    for j in range(start + 1, _block_end(lines, start)):
        found = _key(lines[j]) if _is_content(lines[j]) else None
        if found is not None and fold(found) == fold(key):
            if lines[j + 1 : j + 2] and _is_content(lines[j + 1]) and _indent(lines[j + 1]) > _indent(lines[j]):
                raise ValueError(f"'{found}' satırı birden çok satıra yayılmış; dosyayı elle düzenleyin")
            del lines[j]
            return True
    return False


def remove_ended(text: str, merchant: str) -> str:
    """Take a payment off `_biten`: it is expected again."""
    lines = _lines(text)
    start = _top(lines, "_BITEN")
    if start is None or not _drop_entry(lines, start, merchant):
        raise ValueError(f"'{merchant}' kişisel kurallarda bitmiş olarak yazılı değil")
    return "".join(lines)


def set_merchant_necessity(text: str, merchant: str, level: str) -> str:
    """How necessary a merchant's spending is, whatever its category says (`_gereklilik_işyeri`); level is the
    level's label as the file writes it ("Gerekli", "İsteğe bağlı", "Gereksiz")."""
    if not merchant.strip():
        raise ValueError("işyeri adı gerekli")
    lines = _lines(text)
    entry = f"  {_scalar(merchant.strip(), key=True)}: {_scalar(level, key=True)}\n"
    start = _top(lines, "_GEREKLILIK_ISYERI")
    if start is None:
        gap = "\n" if lines and lines[-1].strip() else ""
        return "".join(lines) + (
            f"{gap}# Kategorisinden farklı değerlendirdiğiniz işyerleri: işyeri adı ve gereklilik düzeyi.\n"
            "_gereklilik_işyeri:\n" + entry
        )
    if re.match(r"^[^#]*:\s*\{\}", lines[start]):
        lines[start] = re.sub(r":\s*\{\}", ":", lines[start], count=1)
    end = _block_end(lines, start)
    for j in range(start + 1, end):
        key = _key(lines[j]) if _is_content(lines[j]) else None
        if key is not None and fold(key) == fold(merchant):  # the entry keeps its spelling and its comment
            comment = re.search(r"\s+#.*$", lines[j].rstrip("\n"))
            lines[j] = f"  {_scalar(key, key=True)}: {_scalar(level, key=True)}{comment[0] if comment else ''}\n"
            return "".join(lines)
    lines.insert(end, entry)
    return "".join(lines)


def remove_merchant_necessity(text: str, merchant: str) -> str:
    """The merchant's spending is as necessary as its category says again."""
    lines = _lines(text)
    start = _top(lines, "_GEREKLILIK_ISYERI")
    if start is None or not _drop_entry(lines, start, merchant):
        raise ValueError(f"'{merchant}' için kişisel kurallarda ayrı bir gereklilik yazılı değil")
    return "".join(lines)


def _regular_items(lines: list[str], start: int) -> tuple[list[str] | None, list[int]]:
    """`_düzenli` as a flow list on its own line (its items), or as a block list (the lines of its items)."""
    head = lines[start].strip()
    after = head.split(":", 1)[1].split("#", 1)[0].strip() if ":" in head else ""
    if after.startswith("["):
        try:
            loaded = yaml.safe_load(after)
        except yaml.YAMLError as exc:
            raise ValueError("_düzenli satırı okunamadı; dosyayı elle düzenleyin") from exc
        if not isinstance(loaded, list):
            raise ValueError("_düzenli bir liste olmalı")
        return [str(item) for item in loaded], []
    found = [j for j in range(start + 1, _block_end(lines, start)) if lines[j].lstrip().startswith("- ")]
    return None, found


def add_regular(text: str, category: str) -> str:
    """A category of commitments (`_düzenli`): its payments are regular even when the amount changes."""
    if not category.strip():
        raise ValueError("kategori adı gerekli")
    category = category.strip()
    lines = _lines(text)
    start = _top(lines, "_DUZENLI")
    if start is None:
        gap = "\n" if lines and lines[-1].strip() else ""
        return "".join(lines) + (
            f"{gap}# Taahhüt kategorileri: tutarı değişse de bu kategorilerdeki ödemeler düzenli sayılır.\n"
            f"_düzenli:\n  - {_scalar(category)}\n"
        )
    flow, items = _regular_items(lines, start)
    if flow is not None:
        if any(fold(c) == fold(category) for c in flow):
            return "".join(lines)
        comment = _trailing_comment(lines[start].strip(), {_key(lines[start]): flow})
        lines[start] = (
            f"{lines[start].split(':', 1)[0]}: [{', '.join(_scalar(c) for c in [*flow, category])}]{comment}\n"
        )
        return "".join(lines)
    if any(fold(lines[j].lstrip()[2:].split("#", 1)[0].strip().strip("\"'")) == fold(category) for j in items):
        return "".join(lines)
    if re.match(r"^[^#]*:\s*\[\s*\]", lines[start]):  # "_düzenli: []"
        lines[start] = re.sub(r":\s*\[\s*\]", ":", lines[start], count=1)
    lines.insert(_block_end(lines, start), f"  - {_scalar(category)}\n")
    return "".join(lines)


def remove_regular(text: str, category: str) -> str:
    """The category is no longer one of commitments in the user's own rules (one shipped with the app stays)."""
    lines = _lines(text)
    start = _top(lines, "_DUZENLI")
    if start is not None:
        flow, items = _regular_items(lines, start)
        if flow is not None and any(fold(c) == fold(category) for c in flow):
            kept = [c for c in flow if fold(c) != fold(category)]
            comment = _trailing_comment(lines[start].strip(), {_key(lines[start]): flow})
            lines[start] = f"{lines[start].split(':', 1)[0]}: [{', '.join(_scalar(c) for c in kept)}]{comment}\n"
            return "".join(lines)
        for j in items:
            if fold(lines[j].lstrip()[2:].split("#", 1)[0].strip().strip("\"'")) == fold(category):
                del lines[j]
                return "".join(lines)
    raise ValueError(f"'{category}' kişisel kurallarda düzenli ödeme kategorisi olarak yazılı değil")
