"""Module 07: wrap it all in an MCP server, sandbox it, and test it over real stdio.

A complete, minimal logs server in one file: ISO-timestamped text logs (plain or gzip),
seven tools. Everything in it was built in modules 01-06; here it is wired together.

    python main.py                   # self-test: launches this file as a real MCP server
    python main.py --serve --dir D   # run the server (this is what an MCP client launches)
"""

from __future__ import annotations

import argparse
import asyncio
import calendar
import functools
import gzip
import os
import re
import sys
import tempfile
import time
from collections import Counter, deque
from collections.abc import Iterator
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer(
    "mini-logs",
    instructions="Investigate big ISO-timestamped logs. Start with log_overview, then error_clusters, "
    "timeline, search_logs. Times are UTC, written 'YYYY-MM-DD HH:MM:SS'.",
)

ALLOWED: list[str] = []
LEVELS = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
ISO = re.compile(rb"^\W{0,3}(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)")
LEVEL = re.compile(rb"\b(TRACE|DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\b")
NORMALIZE = [
    (re.compile(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b"), "<uuid>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"\b[0-9a-fA-F]{8,}\b"), "<hex>"),
    (re.compile(r"(?<![\w<])-?\d+(?:\.\d+)?(?=[A-Za-z]{0,3}(?![\w>]))"), "<n>"),
]
MAX_OUT = 8000
ALIASES = {"WARNING": "WARN", "CRITICAL": "FATAL"}


class ToolFailure(Exception):
    """Expected, explainable failures. The SDK only shows clients a ToolError's text."""


def tool(fn: Callable[..., str]) -> Callable[..., str]:
    @functools.wraps(fn)
    def wrapper(*a: Any, **kw: Any) -> str:
        try:
            out = fn(*a, **kw)
        except (ToolFailure, OSError, ValueError, re.error) as e:
            raise ToolError(str(e)) from e
        return out if len(out) <= MAX_OUT else out[:MAX_OUT] + f"\n... [cut at {MAX_OUT} characters]"

    mcp.tool()(wrapper)
    return fn


# ---- sandbox (module 06's lesson: the server is only as safe as its path check) ----------


def resolve(path: str) -> str:
    roots = [os.path.realpath(r) for r in (ALLOWED or [os.getcwd()])]
    cand = path if os.path.isabs(path) else os.path.join(roots[0], path)
    real = os.path.realpath(cand)  # follows symlinks and '..' BEFORE the check
    if not any(os.path.normcase(real).startswith(os.path.normcase(r) + os.sep) for r in roots):
        raise ToolFailure(f"{path!r} is outside the allowed directories ({', '.join(roots)}); start the server with --dir")
    if not os.path.isfile(real):
        raise ToolFailure(f"no such log file: {path!r}. Paths may be absolute or relative to an allowed directory.")
    return real


# ---- events (modules 01-04) --------------------------------------------------------------


class Ev:
    __slots__ = ("ts", "level", "lines", "lineno")

    def __init__(self, ts: float, level: int | None, first: bytes, lineno: int) -> None:
        self.ts, self.level, self.lines, self.lineno = ts, level, [first], lineno

    def text(self) -> str:
        return "\n".join(ln.decode("utf-8", "replace") for ln in self.lines[:12])


def events(path: str) -> Iterator[Ev]:
    opener = gzip.open if open(path, "rb").read(2) == b"\x1f\x8b" else open
    cur: Ev | None = None
    with opener(path, "rb") as f:  # type: ignore[operator]
        for n, raw in enumerate(f, 1):
            line = raw.rstrip(b"\r\n")
            m = ISO.match(line)
            if m:
                if cur:
                    yield cur
                lv = LEVEL.search(line, 0, 240)
                level = None if not lv else LEVELS.index(ALIASES.get(lv.group(1).decode(), lv.group(1).decode()))
                stamp = float(calendar.timegm(tuple(int(g) for g in m.groups()) + (0, 0, 0)))  # type: ignore[arg-type]
                cur = Ev(stamp, level, line, n)
            elif cur and len(cur.lines) < 200:
                cur.lines.append(line)
    if cur:
        yield cur


def when(s: str | None) -> float | None:
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d\d)-(\d\d)(?:[T ](\d\d):(\d\d)(?::(\d\d))?)?$", s.strip())
    if not m:
        raise ToolFailure(f"cannot parse time {s!r}: use 'YYYY-MM-DD HH:MM:SS' (UTC)")
    y, mo, d, h, mi, sec = (int(g or 0) for g in m.groups())
    return float(calendar.timegm((y, mo, d, h, mi, sec, 0, 0, 0)))


def show(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))


def template(ev: Ev) -> str:
    t = re.sub(r"^\W*\d{4}-\d\d-\d\d[T ][\d:,.]+Z?\W*", "", ev.lines[0].decode("utf-8", "replace"))
    t = re.sub(r"^(?:TRACE|DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\W*", "", t)
    for rx, rep in NORMALIZE:
        t = rx.sub(rep, t)
    exc = [ln.decode("utf-8", "replace") for ln in ev.lines[1:] if ln[:1] not in (b" ", b"\t") and re.search(rb"(Error|Exception)\b", ln)]
    if exc:
        t += " || " + re.sub(r"\d+", "<n>", exc[-1])
    return t[:200]


# ---- tools ---------------------------------------------------------------------------------


@tool
def log_overview(path: str) -> str:
    """Start here. Line count, event count, time range and level histogram of a log file (plain or .gz)."""
    p = resolve(path)
    n = 0
    hist: Counter[str] = Counter()
    first = last = None
    for ev in events(p):
        n += 1
        hist[LEVELS[ev.level] if ev.level is not None else "none"] += 1
        first = ev.ts if first is None else first
        last = ev.ts
    return f"{n} events, {show(first) if first else '-'} .. {show(last) if last else '-'} UTC\nlevels: " + ", ".join(f"{k} {v}" for k, v in hist.most_common())


@tool
def search_logs(path: str, pattern: str, since: str | None = None, until: str | None = None, max_matches: int = 20) -> str:
    """Events containing `pattern` (case-insensitive text) in a time window. Capped at max_matches (max 100); says how many more exist."""
    if not 1 <= max_matches <= 100:
        raise ToolFailure("max_matches must be between 1 and 100")
    s, u, rx = when(since), when(until), re.compile(re.escape(pattern), re.I)
    total, kept = 0, []
    for ev in events(resolve(path)):
        if (s and ev.ts < s) or (u and ev.ts >= u) or not rx.search(ev.text()):
            continue
        total += 1
        if len(kept) < max_matches:
            kept.append(f"{path}:{ev.lineno} [{show(ev.ts)}] {ev.text()}")
    more = f" ({total - len(kept)} more not shown)" if total > len(kept) else ""
    return f"{total} match(es){more}\n" + "\n".join(kept)


@tool
def error_clusters(path: str, level: str = "ERROR", top: int = 10) -> str:
    """Group events at or above `level` into templates (numbers, ips, uuids, hex ids replaced) with counts and an example."""
    if level.upper() not in LEVELS:
        raise ToolFailure(f"unknown level {level!r}: use one of {', '.join(LEVELS)}")
    lo = LEVELS.index(level.upper())
    counts: Counter[str] = Counter()
    example: dict[str, Ev] = {}
    for ev in events(resolve(path)):
        if ev.level is not None and ev.level >= lo:
            t = template(ev)
            counts[t] += 1
            example.setdefault(t, ev)
    return "\n".join(f"x{c}  {t}\n    e.g. [{show(example[t].ts)}] {example[t].lines[0].decode('utf-8', 'replace')[:150]}" for t, c in counts.most_common(top)) or "no events at that level"


@tool
def timeline(path: str, pattern: str = "", bucket_seconds: int = 60) -> str:
    """Event counts per bucket (optionally only events containing `pattern`) with a bar per bucket."""
    if bucket_seconds < 1:
        raise ToolFailure("bucket_seconds must be positive")
    rx = re.compile(re.escape(pattern), re.I)
    counts: Counter[int] = Counter()
    for ev in events(resolve(path)):
        if rx.search(ev.text()):
            counts[int(ev.ts // bucket_seconds)] += 1
    if not counts:
        return "no matching events"
    if len(counts) > 120:
        raise ToolFailure(f"{len(counts)} buckets is too many to print; use a larger bucket_seconds")
    peak = max(counts.values())
    return "\n".join(f"{show(b * bucket_seconds)} {c:>6} {'#' * max(1, c * 40 // peak)}" for b, c in sorted(counts.items()))


@tool
def tail_logs(path: str, lines: int = 20) -> str:
    """The last `lines` events (max 200) of a log file."""
    if not 1 <= lines <= 200:
        raise ToolFailure("lines must be between 1 and 200")
    ring: deque[Ev] = deque(maxlen=lines)
    for ev in events(resolve(path)):
        ring.append(ev)
    return "\n".join(ev.text() for ev in ring)


@tool
def trace_request(path: str, request_id: str) -> str:
    """Every event mentioning a request/correlation id (min 4 characters), in time order."""
    if len(request_id) < 4:
        raise ToolFailure("request_id must be at least 4 characters")
    hits = sorted((ev for ev in events(resolve(path)) if request_id in ev.text()), key=lambda e: e.ts)
    return f"{len(hits)} event(s)\n" + "\n".join(f"[{show(e.ts)}] {e.text()}" for e in hits[:100])


@tool
def compare_windows(path: str, window_minutes: int = 60, level: str = "ERROR") -> str:
    """Templates NEW or SPIKED (3x rate) in the last `window_minutes` of the log versus the window before."""
    lo = LEVELS.index(level.upper()) if level.upper() in LEVELS else 4
    evs = [e for e in events(resolve(path)) if e.level is not None and e.level >= lo]
    if not evs:
        return "no events at that level"
    end = max(e.ts for e in evs) + 1
    w = window_minutes * 60
    a, b = Counter(template(e) for e in evs if end - 2 * w <= e.ts < end - w), Counter(template(e) for e in evs if end - w <= e.ts < end)
    new = [f"NEW   x{c}  {t}" for t, c in b.most_common() if t not in a]
    spiked = [f"SPIKE x{a[t]} -> x{c}  {t}" for t, c in b.most_common() if t in a and c >= 3 and c >= 3 * a[t]]
    return "\n".join(new + spiked) or "nothing new or spiking"


# ---- the self-test: a REAL client, a REAL server process, a REAL file --------------------------


async def self_test() -> None:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    with tempfile.TemporaryDirectory() as root:
        allowed = os.path.join(root, "logs")
        os.mkdir(allowed)
        with open(os.path.join(root, "secret.log"), "w", newline="\n") as f:
            f.write("2026-11-06 10:00:00 INFO secret\n")
        lines = []
        for i in range(600):  # 10 minutes of traffic; errors change character in the last 3 minutes
            t = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(calendar.timegm((2026, 11, 6, 10, 0, 0, 0, 0, 0)) + i))
            if i >= 420 and i % 5 == 0:
                lines.append(f"{t} ERROR payment gateway down code={500 + i}")
                lines.append("RuntimeError: gateway 502")
            elif i % 20 == 0:
                lines.append(f"{t} ERROR db timeout after {3000 + i}ms to 10.0.0.{i % 9}:5432")
            else:
                lines.append(f"{t} INFO  req={i:08x} ok")
        with open(os.path.join(allowed, "app.log"), "w", newline="\n") as f:
            f.write("\n".join(lines) + "\n")

        params = StdioServerParameters(command=sys.executable, args=[__file__, "--serve", "--dir", allowed])
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
            assert names == {"log_overview", "search_logs", "error_clusters", "timeline", "tail_logs", "trace_request", "compare_windows"}, names

            async def call(name: str, **args: Any) -> tuple[bool, str]:
                res = await s.call_tool(name, args)
                return bool(res.is_error), res.content[0].text  # type: ignore[union-attr]

            err, out = await call("log_overview", path="app.log")
            assert not err and "600 events" in out and "ERROR" in out, out
            err, out = await call("error_clusters", path="app.log")
            assert "db timeout after <n>ms to <ip>" in out and "payment gateway down code=<n> || RuntimeError: gateway <n>" in out, out
            err, out = await call("search_logs", path="app.log", pattern="gateway down", max_matches=3)
            assert "(" in out.split("\n")[0] and "more not shown" in out, out
            err, out = await call("timeline", path="app.log", pattern="gateway", bucket_seconds=60)
            assert "###" in out, out
            err, out = await call("compare_windows", path="app.log", window_minutes=3)
            assert "NEW   x36  " in out and "payment gateway down" in out, out
            err, out = await call("trace_request", path="app.log", request_id="00000065")
            assert out.startswith("1 event(s)"), out
            err, out = await call("tail_logs", path="app.log", lines=2)
            assert not err and out.count("\n") >= 1

            # the errors an agent must be able to read
            for args, needle in [
                (dict(path=os.path.join(root, "secret.log")), "outside the allowed"),
                (dict(path="../secret.log"), "outside the allowed"),
                (dict(path="nope.log"), "no such log file"),
            ]:
                err, out = await call("log_overview", **args)
                assert err and needle in out, (args, out)
            err, out = await call("search_logs", path="app.log", pattern="x", since="yesterday")
            assert err and "cannot parse time" in out, out
            print("module 07 ok: 7 tools, sandbox, errors verified over real stdio")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--dir", action="append", default=[])
    args = ap.parse_args()
    if args.serve:
        ALLOWED.extend(args.dir)
        mcp.run()  # stdout carries JSON-RPC: never print() to it in serve mode
    else:
        asyncio.run(self_test())


if __name__ == "__main__":
    main()
