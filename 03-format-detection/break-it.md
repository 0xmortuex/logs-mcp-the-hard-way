# Break It: Format Detection

## Challenge 1: Let Indented Lines Vote

Remove the filter that drops indented lines from `top`, then feed `detect` 5 JSON lines followed by a
Python traceback of 12 indented lines.

**Hint:** The indented lines vote for nothing, but they still count in the denominator `len(top)`, so
the winner falls below 50% and the file is labelled `plain`. Real Java services do exactly this.

## Challenge 2: Case-Insensitive Levels

Make `L_WORD` case-insensitive and call `level` on `2026-11-06 12:30:00 request done, error handled`.

**Hint:** The line becomes ERROR. On a busy service every line that mentions "error" in prose now
pollutes the error histogram.

## Challenge 3: Swap the Order

Put `("iso", ISO_AT)` before `("access", ACCESS)` in the loop and run the access-log sample. Does it
still pass? Now try an access log whose lines begin with a timestamp.

**Hint:** Standard combined logs start with an IP, so ISO misses them either way; some proxies put a
timestamp first, and then only the order decides.
