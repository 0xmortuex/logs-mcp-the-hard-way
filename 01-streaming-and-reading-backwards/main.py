"""Module 01: stream a file you cannot load, and read it backwards.

Run:  python main.py        (self-checking; exits non-zero on failure)
"""

from __future__ import annotations

import gzip
import io
import os
import tempfile
import tracemalloc
from collections.abc import Iterator


def make_log(path: str, n: int) -> None:
    """A boring but realistic log: n lines, ~90 bytes each."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for i in range(n):
            sec = i // 20
            f.write(
                f"2026-11-06 {sec // 3600 % 24:02d}:{sec // 60 % 60:02d}:{sec % 60:02d},{i % 20 * 50:03d} "
                f"INFO  [worker-{i % 8}] handled GET /api/users/{i} in {i % 90}ms\n"
            )


# --------------------------------------------------------------- forward ----


def open_stream(path: str) -> io.BufferedReader:
    """Plain and gzip files behind one interface. Always bytes: decoding is
    expensive and most lines never need it."""
    with open(path, "rb") as f:
        magic = f.read(2)
    if magic == b"\x1f\x8b":  # sniff the content, not the name: rotated files get renamed
        return io.BufferedReader(gzip.open(path, "rb"), 1 << 20)  # type: ignore[arg-type]
    return open(path, "rb", buffering=1 << 20)


def lines(path: str) -> Iterator[bytes]:
    """Constant memory: the file object yields one line at a time."""
    with open_stream(path) as f:
        for raw in f:
            yield raw.rstrip(b"\r\n")


def count_lines(path: str) -> int:
    """Counting newlines in big blocks is far faster than iterating lines."""
    n, last = 0, b"\n"
    with open_stream(path) as f:
        while block := f.read(1 << 20):
            n += block.count(b"\n")
            last = block[-1:]
    return n + (0 if last == b"\n" else 1)  # last line may lack a newline


# -------------------------------------------------------------- backwards ----


def reverse_lines(path: str, block_size: int = 1 << 16) -> Iterator[bytes]:
    """Yield lines from the END of a plain file without reading the rest.

    Read blocks from the end. A block almost never starts or ends on a line
    boundary, so the first (partial) piece of each block is carried into the
    next, earlier block, where it becomes the END of a complete line.
    """
    with open(path, "rb") as f:
        pos = f.seek(0, os.SEEK_END)
        carry = b""
        first = True
        while pos > 0:
            step = min(block_size, pos)
            pos -= step
            f.seek(pos)
            parts = (f.read(step) + carry).split(b"\n")
            carry = parts[0]
            for line in reversed(parts[1:]):
                if first:
                    first = False
                    if line == b"":  # file ended with "\n": there is no empty last line
                        continue
                yield line.rstrip(b"\r")
        if not (first and carry == b""):
            yield carry.rstrip(b"\r")


def tail(path: str, n: int) -> list[bytes]:
    out = []
    for line in reverse_lines(path):
        out.append(line)
        if len(out) == n:
            break
    return out[::-1]


# ------------------------------------------------------------------ demo ----


def peak_memory(fn) -> int:  # type: ignore[no-untyped-def]
    tracemalloc.start()
    fn()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "app.log")
        make_log(path, 200_000)
        size = os.path.getsize(path)
        print(f"file: {size / 1e6:.1f} MB, {count_lines(path)} lines")

        # 1. forward streaming matches the naive approach
        with open(path, "rb") as f:
            naive = f.read().splitlines()
        assert list(lines(path)) == naive
        assert count_lines(path) == len(naive) == 200_000

        # 2. ... but uses a sliver of the memory
        stream_peak = peak_memory(lambda: sum(1 for ln in lines(path) if b"in 89ms" in ln))
        naive_peak = peak_memory(lambda: sum(1 for ln in open(path, "rb").read().splitlines() if b"in 89ms" in ln))
        print(f"peak memory  stream: {stream_peak / 1e6:.2f} MB   read-everything: {naive_peak / 1e6:.2f} MB")
        assert stream_peak < size / 5 < naive_peak

        # 3. reading backwards agrees with reading forwards, at any block size
        for bs in (7, 100, 4096, 1 << 16):
            got = list(reverse_lines(path, bs))
            assert got == naive[::-1], bs
        assert tail(path, 3) == naive[-3:]

        # 4. edge cases: no trailing newline, CRLF, tiny and empty files
        for text, expect in [
            (b"a\nb\nc", [b"a", b"b", b"c"]),
            (b"a\r\nb\r\n", [b"a", b"b"]),
            (b"x\n", [b"x"]),
            (b"\n", [b""]),
            (b"", []),
        ]:
            p = os.path.join(d, "edge")
            with open(p, "wb") as f:
                f.write(text)
            assert list(reverse_lines(p, 2)) == expect[::-1], text
            assert list(lines(p)) == expect, text

        # 5. gzip uses the same forward API (but cannot seek backwards cheaply)
        gz = os.path.join(d, "app.log.1.gz")
        with gzip.open(gz, "wb") as g:
            g.write(b"\n".join(naive) + b"\n")
        assert list(lines(gz)) == naive and count_lines(gz) == 200_000

        # 6. tail touches only the end of the file: memory is one block, not the file
        tail_peak = peak_memory(lambda: tail(path, 100))
        print(f"tail(100) peak memory: {tail_peak / 1e3:.0f} KB for a {size / 1e6:.0f} MB file")
        assert tail_peak < 1 << 20
    print("module 01 ok")


if __name__ == "__main__":
    main()
