"""Module 02: parse timestamps to UTC epoch seconds, fast, across formats and zones.

Run:  python main.py
"""

from __future__ import annotations

import calendar
import re
import time

# One regex per family. They run on BYTES and are anchored near the start of the line:
# a line only "starts an event" if its timestamp is where a timestamp should be.
ISO = re.compile(
    rb"^\W{0,3}(\d{4}[-/]\d\d[-/]\d\d[T ]\d\d:\d\d:\d\d)(?:[.,](\d{1,9}))?(Z|[+-]\d\d:?\d\d)?"
)
CLF = re.compile(rb"\[(\d\d)/([A-Z][a-z]{2})/(\d{4}):(\d\d):(\d\d):(\d\d) ([+-]\d{4})\]")
SYSLOG = re.compile(rb"^([A-Z][a-z]{2}) ([ \d]\d) (\d\d):(\d\d):(\d\d)\b")
KEYED = re.compile(  # JSON / logfmt: "time":"..." , ts=1730000000.5
    rb"""(?:^|[\s,{])"?(?:@timestamp|timestamp|time|ts|datetime|t)"?\s*[:=]\s*"?"""
    rb"""(\d{4}[-/]\d\d[-/]\d\d[T ]\d\d:\d\d:\d\d[^\s",}]*|\d{9,}(?:\.\d+)?)"""
)
MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def tz_seconds(tz: bytes | None, default: int) -> int:
    """b'Z' -> 0, b'+02:00' -> 7200, None -> the default the caller assumes."""
    if tz is None:
        return default
    if tz == b"Z":
        return 0
    sign = -1 if tz[:1] == b"-" else 1
    d = tz[1:].replace(b":", b"")
    return sign * (int(d[:2]) * 3600 + int(d[2:4]) * 60)


class Parser:
    def __init__(self, assume_tz: int = 0, file_mtime: float = 0.0) -> None:
        self.assume_tz = assume_tz
        self.mtime = file_mtime
        # Consecutive lines share the same second: cache the calendar math.
        self._cache: dict[bytes, int] = {}

    def iso(self, line: bytes) -> float | None:
        m = ISO.match(line)
        if not m:
            return None
        key = m.group(1)
        base = self._cache.get(key)
        if base is None:
            base = calendar.timegm(
                (int(key[0:4]), int(key[5:7]), int(key[8:10]), int(key[11:13]), int(key[14:16]), int(key[17:19]), 0, 0, 0)
            )
            self._cache[key] = base
        frac = m.group(2)
        # An explicit zone wins. Otherwise assume one: guessing is unavoidable, hiding the guess is not.
        return base + (int(frac) / 10 ** len(frac) if frac else 0.0) - tz_seconds(m.group(3), self.assume_tz)

    def clf(self, line: bytes) -> float | None:
        m = CLF.search(line, 0, 160)
        if not m:
            return None
        local = calendar.timegm(
            (int(m.group(3)), MONTHS[m.group(2).decode()], int(m.group(1)), int(m.group(4)), int(m.group(5)), int(m.group(6)), 0, 0, 0)
        )
        return local - tz_seconds(m.group(7), 0)

    def syslog(self, line: bytes) -> float | None:
        """No year in the line! Use the file's mtime: an entry cannot be newer than the
        file's last write, so take the latest year that does not put it in the future."""
        m = SYSLOG.match(line)
        if not m:
            return None
        mon = MONTHS[m.group(1).decode()]
        day, hh, mi, ss = (int(m.group(i)) for i in (2, 3, 4, 5))
        mtime_year = time.gmtime(self.mtime).tm_year
        for y in (mtime_year, mtime_year - 1):
            t = calendar.timegm((y, mon, day, hh, mi, ss, 0, 0, 0)) - self.assume_tz
            if t <= self.mtime + 86400:
                return float(t)
        return None

    def keyed(self, line: bytes) -> float | None:
        m = KEYED.search(line)
        if not m:
            return None
        v = m.group(1)
        if v[4:5] in (b"-", b"/"):
            return self.iso(v)
        x = float(v)  # epoch: seconds, milliseconds or microseconds. Magnitude tells which.
        return x / 1e6 if x > 1e14 else x / 1e3 if x > 1e11 else x


def main() -> None:
    T = calendar.timegm((2026, 11, 6, 12, 30, 0, 0, 0, 0))
    p = Parser(assume_tz=3600, file_mtime=float(calendar.timegm((2027, 1, 2, 0, 0, 0, 0, 0, 0))))

    # ISO: the zone on the line wins; a naive timestamp uses the assumed zone (+01:00 here)
    assert p.iso(b"2026-11-06T12:30:00Z INFO x") == T
    assert p.iso(b"2026-11-06T12:30:00.5+02:00 x") == T - 7200 + 0.5
    assert p.iso(b"2026-11-06 12:30:00,250 INFO x") == T - 3600 + 0.25  # Python logging uses a comma
    assert p.iso(b"2026/11/06 12:30:00 [error] nginx") == T - 3600
    assert p.iso(b"    at com.example.Foo(Foo.java:10)") is None  # a continuation line

    # Same instant, three zones -> same number. This is what makes cross-service tracing possible.
    a = p.iso(b"2026-11-06T10:00:00Z x")
    b = p.iso(b"2026-11-06T12:00:00+02:00 x")
    c = p.iso(b"2026-11-06T05:00:00-0500 x")
    assert a == b == c

    # Access logs
    assert p.clf(b'1.2.3.4 - - [06/Nov/2026:14:30:00 +0200] "GET / HTTP/1.1" 200 5') == T

    # Syslog: file last written 2027-01-02, so Dec 31 is 2026 and Jan 1 is 2027
    assert p.syslog(b"Dec 31 23:59:59 host sshd[1]: x") == calendar.timegm((2026, 12, 31, 23, 59, 59, 0, 0, 0)) - 3600
    assert p.syslog(b"Jan  1 00:00:05 host sshd[1]: x") == calendar.timegm((2027, 1, 1, 0, 0, 5, 0, 0, 0)) - 3600

    # JSON and logfmt, ISO strings and epoch numbers in any unit
    assert p.keyed(b'{"level":"error","time":"2026-11-06T12:30:00Z"}') == T
    assert p.keyed(b'{"ts":%d}' % (T * 1000)) == T
    assert p.keyed(b"ts=%d.5 level=info" % T) == T + 0.5
    print("module 02 ok")


if __name__ == "__main__":
    main()
