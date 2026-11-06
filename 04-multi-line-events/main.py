"""Module 04: group physical lines into EVENTS (a start line plus its continuation lines).

Run:  python main.py
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

ISO_AT = re.compile(rb"^\W{0,3}\d{4}[-/]\d\d[-/]\d\d[T ]\d\d:\d\d:\d\d")
MAX_EVENT_LINES = 200  # a runaway trace must not eat memory


class Event:
    __slots__ = ("lineno", "lines", "nlines", "tail")

    def __init__(self, lineno: int, first: bytes) -> None:
        self.lineno = lineno
        self.lines = [first]
        self.nlines = 1
        self.tail: bytes | None = None  # always remember the LAST line: it is the exception

    def add(self, line: bytes) -> None:
        self.nlines += 1
        if len(self.lines) < MAX_EVENT_LINES:
            self.lines.append(line)
        else:
            self.tail = line

    def text(self) -> bytes:
        return b"\n".join(self.lines)


def events(lines: Iterable[bytes], starts_event=lambda ln: ISO_AT.match(ln) is not None) -> Iterator[Event]:  # type: ignore[no-untyped-def]
    """Streaming grouper: holds ONE event at a time, so memory stays flat.

    A line that starts an event begins a new one. Anything else is glued to the
    previous event - this is the rule that makes every stack trace format work
    without knowing any of them.
    """
    cur: Event | None = None
    for n, line in enumerate(lines, 1):
        if starts_event(line):
            if cur is not None:
                yield cur
            cur = Event(n, line)
        elif cur is not None:
            cur.add(line)
        else:
            cur = Event(n, line)  # junk before the first timestamp is its own event
    if cur is not None:
        yield cur


def indent_or_marker(line: bytes) -> bool:
    """For files WITHOUT timestamps we cannot use 'has a timestamp'. Fall back to
    'looks like a continuation' - indentation and well-known trace markers."""
    return not (line[:1] in (b" ", b"\t") or line.startswith((b"Caused by", b"Traceback (most", b"... ")))


LOG = b"""2026-11-06 10:00:00,100 INFO  boot
2026-11-06 10:00:01,200 ERROR charge failed order=7
Traceback (most recent call last):
  File "pay.py", line 9, in charge
    gateway.post(order)
ConnectionResetError: peer reset
2026-11-06 10:00:02,000 WARN  java service
2026-11-06 10:00:02,500 ERROR request failed
java.lang.IllegalStateException: bad state
\tat com.shop.Cart.add(Cart.java:42)
\tat com.shop.Api.post(Api.java:7)
Caused by: java.io.IOException: disk full
\tat java.base/java.io.FileOutputStream.write(Native Method)
\t... 3 more
2026-11-06 10:00:03,000 INFO  done
""".split(b"\n")[:-1]


def main() -> None:
    evs = list(events(LOG))
    assert len(evs) == 5, len(evs)  # 15 physical lines, 5 events
    assert [e.nlines for e in evs] == [1, 5, 1, 7, 1]
    assert b"ConnectionResetError" in evs[1].text()  # the trace stays with its ERROR line
    assert evs[1].lineno == 2  # and we still know where it starts

    # A runaway trace is capped but its last line survives
    giant = [b"2026-11-06 10:00:00 ERROR boom"] + [b"  at frame%d" % i for i in range(10_000)] + [b"RootCause: it"]
    (ev,) = list(events(giant))
    assert ev.nlines == 10_002 and len(ev.lines) == MAX_EVENT_LINES and ev.tail == b"RootCause: it"

    # Files with no timestamps at all: group by indentation / markers instead
    plain = [b"alpha", b"beta", b"  indented", b"gamma"]
    got = list(events(plain, starts_event=indent_or_marker))
    assert [e.nlines for e in got] == [1, 2, 1]

    # Junk before the first timestamp is kept, not dropped
    assert len(list(events([b"banner", b"2026-11-06 10:00:00 INFO x"]))) == 2
    print("module 04 ok")


if __name__ == "__main__":
    main()
