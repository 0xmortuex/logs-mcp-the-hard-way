# Break It: Streaming and Reading Backwards

## Challenge 1: Remove the Carry

In `reverse_lines`, delete `+ carry` from `parts = (f.read(step) + carry).split(b"\n")`. Run
`main.py`. Which block size fails first, and what do the broken lines look like?

**Hint:** With a 7-byte block almost every read starts mid-line. Without the carry, the front half
of each line is lost and the next block's last piece is glued on wrongly. A 64 KiB block hides the
bug on small files; the tiny sizes in the test exist for exactly this.

## Challenge 2: Keep the Phantom Line

Remove the `if first:` branch that skips the trailing empty string. What does `tail(path, 3)` return
for a file that ends with a newline?

**Hint:** `b"a\nb\n".split(b"\n")` is `[b"a", b"b", b""]`. You now return an empty "line" as the newest
entry, and `tail -n 3` gives only two real lines.

## Challenge 3: Memory

Change `lines()` to `return list(...)` style (build the list, then iterate it) and rerun the memory
check. Then try `tracemalloc` on `count_lines` with `f.read(1 << 30)` as the block size.

**Hint:** The block size in `count_lines` is a memory ceiling: one block plus a copy. The real server's
first benchmark showed a 17 MB peak from an 8 MiB block, which is why it uses 1 MiB.
