"""Module 06: bound everything the agent sees, and skip what it did not ask about.

Run:  python main.py
"""

from __future__ import annotations

import calendar
import os
import re
import time
import tempfile
from collections import deque
from collections.abc import Callable, Iterator

ISO = re.compile(rb"^(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)")


def ts_of(line: bytes) -> float | None:
    m = ISO.match(line)
    return float(calendar.timegm(tuple(int(g) for g in m.groups()) + (0, 0, 0))) if m else None  # type: ignore[arg-type]


def make_log(path: str, n: int) -> None:
    base = calendar.timegm((2026, 11, 6, 0, 0, 0, 0, 0, 0))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for i in range(n):
            t = base + i
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))
            f.write(f"{stamp} {'ERROR' if i % 50 == 0 else 'INFO '} line {i}\n")


# ---------------------------------------------------------------- caps ----

MAX_LINE = 120


def clip(s: str, n: int = MAX_LINE) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


def search(
    lines: Iterator[bytes], matches: Callable[[bytes], bool], max_matches: int = 5, newest_first: bool = False, max_chars: int = 2000
) -> str:
    """Return at most max_matches lines, but ALWAYS count them all.

    - oldest first: keep the first N and keep counting
    - newest first: a ring buffer (deque with maxlen) keeps the last N in O(N) memory
    - the answer says how many more exist, so the agent can decide to narrow the query
      instead of wrongly concluding that what it sees is everything
    """
    kept: deque[bytes] = deque(maxlen=max_matches if newest_first else None)
    total = 0
    for line in lines:
        if matches(line):
            total += 1
            if newest_first or len(kept) < max_matches:
                kept.append(line)
    head = f"{total} match(es); showing {'newest' if newest_first else 'oldest'} {len(kept)}"
    if total > len(kept):
        head += f" ({total - len(kept)} more not shown - narrow the query, raise max_matches, or use newest_first)"
    body = "\n".join(clip(k.decode("utf-8", "replace")) for k in kept)
    out = f"{head}\n{body}"
    if len(out) > max_chars:  # the last line of defence: a hard ceiling on the response
        out = out[:max_chars] + f"\n... [cut at {max_chars} characters]"
    return out


# --------------------------------------------------------------- bisect ----


def first_ts_at(f, offset: int) -> float | None:  # type: ignore[no-untyped-def]
    """Timestamp of the first complete timestamped line at or after a byte offset."""
    f.seek(offset)
    if offset:
        f.readline()  # we landed mid-line: throw the partial line away
    for _ in range(400):
        raw = f.readline()
        if not raw:
            return None
        t = ts_of(raw)
        if t is not None:
            return t
    return None


def bisect_offset(path: str, target: float, window: int = 1 << 16) -> int:
    """A byte offset at or just before the first line with ts >= target.

    Binary search over BYTES, not lines: log files are sorted by time, so we can
    jump. 600 MB needs ~13 probes instead of reading 600 MB. Stop when the bracket
    is small and scan the rest linearly.
    """
    lo, hi = 0, os.path.getsize(path)
    with open(path, "rb") as f:
        while hi - lo > window:
            mid = (lo + hi) // 2
            t = first_ts_at(f, mid)
            if t is None or t >= target:
                hi = mid
            else:
                lo = mid
    return max(0, lo - window)  # back off: an event might straddle the probe


def lines_between(path: str, since: float, until: float, slack: float = 3600.0, counter: list[int] | None = None) -> Iterator[bytes]:
    off = bisect_offset(path, since)
    with open(path, "rb") as f:
        f.seek(off)
        if off:
            f.readline()
        for raw in f:
            t = ts_of(raw)
            if counter is not None:
                counter[0] += 1
            if t is None or t < since:
                continue
            if t >= until:
                if t > until + slack:  # logs are roughly chronological: stop reading
                    return
                continue
            yield raw.rstrip(b"\r\n")


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "app.log")
        make_log(path, 400_000)  # one line per second: about 4.6 days, ~15 MB
        base = calendar.timegm((2026, 11, 6, 0, 0, 0, 0, 0, 0))

        everything = (ln.rstrip(b"\r\n") for ln in open(path, "rb"))
        out = search(everything, lambda ln: b"ERROR" in ln, max_matches=3)
        print(out)
        assert out.startswith("8000 match(es); showing oldest 3 (7997 more not shown")
        newest = search((ln for ln in open(path, "rb")), lambda ln: b"ERROR" in ln, max_matches=3, newest_first=True)
        assert "line 399950" in newest and "line 0" not in newest

        # hard ceilings: an absurd line and a tiny character budget
        long_line = iter([b"x" * 5000])
        assert len(search(long_line, lambda ln: True).split("\n")[1]) == MAX_LINE
        assert "[cut at 50 characters]" in search(iter([b"a" * 90] * 5), lambda ln: True, max_chars=50)

        # bisect: same answer as a full scan, a tiny fraction of the work
        since, until = base + 200_000, base + 200_060
        window = list(lines_between(path, since, until))
        brute = [ln.rstrip(b"\r\n") for ln in open(path, "rb") if (t := ts_of(ln)) is not None and since <= t < until]
        assert window == brute and len(window) == 60
        seen = [0]
        list(lines_between(path, since, until, slack=30.0, counter=seen))  # small slack: this demo log is perfectly ordered
        print(f"bisect examined {seen[0]} of 400000 lines")
        assert seen[0] < 5000
    print("module 06 ok")


if __name__ == "__main__":
    main()
