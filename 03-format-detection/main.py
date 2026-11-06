"""Module 03: detect the format of a log by voting over a sample, and find levels.

Run:  python main.py
"""

from __future__ import annotations

import json
import re

ISO_AT = re.compile(rb"^\W{0,3}\d{4}[-/]\d\d[-/]\d\d[T ]\d\d:\d\d:\d\d")
SYSLOG_AT = re.compile(rb"^[A-Z][a-z]{2} [ \d]\d \d\d:\d\d:\d\d\b")
ACCESS = re.compile(rb'^\S+ \S+ \S+ \[[^\]]+\] "[^"]*" \d{3} ')
LOGFMT = re.compile(rb'^(?:[A-Za-z_][\w.]*=(?:"[^"]*"|\S*)\s+){2,}')


def detect(sample: list[bytes]) -> str:
    """Each line votes for the first format it fits. A format wins with half the votes.

    Votes are only cast by UNINDENTED lines: stack traces are indented, and a Java
    service that logs one trace per error would otherwise look 'plain'.
    """
    top = [ln for ln in sample if ln.strip() and ln[:1] not in (b" ", b"\t")]
    votes = {"json": 0, "access": 0, "syslog": 0, "iso": 0, "logfmt": 0}
    for ln in top:
        if ln.startswith(b"{") and ln.rstrip().endswith(b"}"):
            try:
                json.loads(ln)
                votes["json"] += 1
                continue
            except ValueError:
                pass
        # Order matters: an access log line also contains a date, so test it before ISO.
        for name, rx in (("access", ACCESS), ("syslog", SYSLOG_AT), ("iso", ISO_AT), ("logfmt", LOGFMT)):
            if rx.match(ln):
                votes[name] += 1
                break
    best = max(votes, key=lambda k: votes[k])
    return best if top and votes[best] * 2 >= len(top) else "plain"


def multiline_style(sample: list[bytes]) -> str | None:
    if any(ln.startswith(b"Traceback (most recent call last)") for ln in sample):
        return "python-traceback"
    if any(ln[:1] in (b" ", b"\t") and ln.lstrip().startswith(b"at ") for ln in sample):
        return "java-stack-trace"
    return None


# Levels. Explicit key (json/logfmt) beats bare words; never match lowercase prose.
LEVEL_NAMES = {"trace": 0, "debug": 1, "info": 2, "notice": 2, "warn": 3, "warning": 3, "error": 4, "err": 4,
               "severe": 4, "crit": 5, "critical": 5, "fatal": 5, "panic": 5}
PINO = {10: 0, 20: 1, 30: 2, 40: 3, 50: 4, 60: 5}
L_KEY = re.compile(rb"""(?:level|lvl|severity|levelname)["']?\s*[=:]\s*["']?(\w+)""", re.I)
L_BRACKET = re.compile(rb"\[(debug|info|notice|warn|error|crit|alert|emerg)\]")
L_WORD = re.compile(rb"\b(TRACE|DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|ERR|CRITICAL|CRIT|FATAL|SEVERE|PANIC)\b")
STATUS = re.compile(rb'" (\d{3}) ')


def level(line: bytes, fmt: str) -> int | None:
    if fmt == "access":  # no level words in an access log: derive one from the HTTP status
        m = STATUS.search(line, 0, 400)
        return None if not m else 4 if int(m.group(1)) >= 500 else 3 if int(m.group(1)) >= 400 else 2
    order = (L_KEY, L_WORD) if fmt in ("json", "logfmt") else (L_WORD, L_BRACKET, L_KEY)
    for rx in order:
        m = rx.search(line, 0, 240)  # only the head of the line: messages mention 'ERROR' too
        if m:
            tok = m.group(1).decode()
            v = PINO.get(int(tok)) if tok.isdigit() else LEVEL_NAMES.get(tok.lower())
            if v is not None:
                return v
    return None


SAMPLES = {
    "json": [b'{"level":"info","time":"2026-11-06T12:30:00Z","msg":"a"}'] * 5,
    "logfmt": [b'ts=2026-11-06T12:30:00Z level=info msg="a b" user=1'] * 5,
    "syslog": [b"Nov  6 12:30:00 host app[1]: hello"] * 5,
    "access": [b'1.2.3.4 - - [06/Nov/2026:12:30:00 +0000] "GET / HTTP/1.1" 200 5 "-" "x"'] * 5,
    "iso": [b"2026-11-06 12:30:00,123 INFO hello"] * 5,
    "plain": [b"just some words", b"and more words"] * 3,
}


def main() -> None:
    for name, sample in SAMPLES.items():
        assert detect(sample) == name, name

    # A banner line, a trace and noise do not fool the vote
    noisy = [b"=== starting app v2 ==="] + SAMPLES["iso"] + [b"Traceback (most recent call last):", b'  File "x.py"', b"ValueError: x"]
    assert detect(noisy) == "iso" and multiline_style(noisy) == "python-traceback"
    assert multiline_style(SAMPLES["iso"] + [b"\tat com.a.B.c(B.java:1)"]) == "java-stack-trace"
    assert detect([]) == "plain"

    assert level(b"2026-11-06 12:30:00 ERROR [x] boom", "iso") == 4
    assert level(b"2026/11/06 12:30:00 [crit] 1#1: nginx", "iso") == 5
    assert level(b"2026-11-06 12:30:00 all fine, error handled", "iso") is None  # lowercase prose
    assert level(b'{"level":50,"msg":"x"}', "json") == 4  # pino numeric levels
    assert level(b'ts=1 level=warn msg="ERROR in text"', "logfmt") == 3  # key beats bare word
    assert level(SAMPLES["access"][0].replace(b" 200 ", b" 503 "), "access") == 4
    print("module 03 ok")


if __name__ == "__main__":
    main()
