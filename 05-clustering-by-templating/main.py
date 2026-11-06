"""Module 05: group errors into templates by replacing the variable parts.

Run:  python main.py
"""

from __future__ import annotations

import re
from collections import Counter

# ORDER MATTERS. Specific shapes first, the greedy catch-all (bare numbers) last.
# If numbers ran first, a UUID would be shredded into <n>-<n>-... before we could see it.
RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
    (re.compile(r"\d{4}[-/]\d\d[-/]\d\d[T ]\d\d:\d\d:\d\d(?:[.,]\d+)?(?:Z|[+-]\d\d:?\d\d)?"), "<ts>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"https?://[^\s\"'<>)]+"), "<url>"),
    (re.compile(r"(?:\b[A-Za-z]:\\|(?<![\w<])/)(?:[\w.@+~-]+[/\\])+[\w.@+~-]*"), "<path>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<hex>"),
    (re.compile(r"\b[0-9a-fA-F]{8,}\b"), "<hex>"),  # long hex-looking ids (even all-digit ones)
    # mixed letters+digits tokens (user8f2c1, req-a1b2c3) - but not '3204ms', which is a number with a unit
    (re.compile(r"\b(?!\d+[A-Za-z]{1,3}\b)(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{6,}\b"), "<id>"),
    (re.compile(r"(?<![\w<])-?\d+(?:\.\d+)?(?=[A-Za-z]{0,3}(?![\w>]))"), "<n>"),
]
LEAD = re.compile(  # strip '<ts> LEVEL ' so two levels of the same message still group
    r"^(?:\W{0,2}<ts>[\s:|\]-]{0,3})?(?:\W{0,2}(?:TRACE|DEBUG|INFO|WARNING|WARN|ERROR|ERR|CRITICAL|FATAL)\b[\s:|\]-]{0,3})?"
)
EXC = re.compile(r"^(?:Caused by: )?[\w$.]+(?:Exception|Error|Exit|Interrupt)[\w$.]*\b.*")


def normalize(text: str) -> str:
    for rx, repl in RULES:
        text = rx.sub(repl, text)
    return re.sub(r"\s+", " ", text).strip()


def template(event_lines: list[str]) -> str:
    """First line, normalised, plus the exception line for multi-line events.

    Two different bugs can log the same first line ('charge failed order=7'); the
    exception at the bottom of the trace is what tells them apart.
    """
    t = normalize(event_lines[0])
    t = LEAD.sub("", t, count=1).strip() or t
    exc = [ln for ln in event_lines[1:] if ln[:1] not in (" ", "\t") and EXC.match(ln)]
    return f"{t} || {normalize(exc[-1])}" if exc else t


def cluster(events: list[list[str]], max_templates: int = 5000) -> tuple[Counter[str], int]:
    """Count templates. The dict is capped: an unbounded set of templates is an
    unbounded memory leak the first time a log contains a random token we failed to
    normalise. Overflow is COUNTED, so the report can say so instead of lying."""
    counts: Counter[str] = Counter()
    overflow = 0
    for ev in events:
        t = template(ev)
        if t in counts or len(counts) < max_templates:
            counts[t] += 1
        else:
            overflow += 1
    return counts, overflow


def main() -> None:
    assert normalize("timeout after 3204ms to 10.0.0.5:5432") == "timeout after <n>ms to <ip>"
    assert normalize("user 8f14e45f-ceea-467a-9575-8a6e0d7e1c2b not found") == "user <uuid> not found"
    assert normalize("open /var/log/app/x.log failed") == "open <path> failed"
    assert normalize(r"open C:\logs\app\x.log failed") == "open <path> failed"
    assert normalize("GET https://a.b/c?d=1 -> 502") == "GET <url> -> <n>"
    assert normalize("req=c541013d and req=42472479") == "req=<hex> and req=<hex>"  # all-digit hex-ish ids too
    assert normalize("session user8f2c1 expired") == "session <id> expired"
    assert normalize("retry 3 of 5, took 1.5s") == "retry <n> of <n>, took <n>s"

    # Level and timestamp prefixes do not split a message
    a = template(["2026-11-06 10:00:00,100 ERROR [db] timeout after 31ms"])
    b = template(["2026-11-06 11:00:09,900 FATAL [db] timeout after 4000ms"])
    assert a == b == "[db] timeout after <n>ms", (a, b)

    # Same first line, different root cause -> different clusters
    c1 = template(["... ERROR charge failed order=7", "Traceback (most recent call last):", '  File "x.py", line 9', "KeyError: 'sku'"])
    c2 = template(["... ERROR charge failed order=8", "Traceback (most recent call last):", '  File "x.py", line 9', "ValueError: bad sku 12"])
    assert c1 != c2 and c2.endswith("ValueError: bad sku <n>")

    evs = [[f"2026-11-06 10:00:{i % 60:02d} ERROR timeout after {i}ms to 10.0.0.{i % 9}:80"] for i in range(1000)]
    evs += [[f"2026-11-06 10:00:00 ERROR weird token {i:08x}zz{i}"] for i in range(50)]
    counts, overflow = cluster(evs)
    assert counts.most_common(1)[0][1] == 1000 and overflow == 0

    # The cap: unique tokens we fail to normalise cannot grow memory without bound
    unique = [[f"ERROR {chr(97 + i % 26)}{'x' * (i // 26)} unique message"] for i in range(300)]
    counts, overflow = cluster(unique, max_templates=100)
    assert len(counts) == 100 and overflow == 200
    print("module 05 ok")


if __name__ == "__main__":
    main()
