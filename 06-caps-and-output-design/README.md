# Module 06: Caps and Output Design

## The Concept

Everything the tool returns lands in the agent's context window. A tool that answers "search for
`timeout`" with 400,000 lines does not give the agent more information. It destroys the conversation.
So the output has to be designed as carefully as the input.

Four rules, all in `main.py`:

**1. Hard caps on every axis.** Matches (`max_matches`), characters per line (`clip`), characters
per response (`max_chars`), lines per event, templates. A hostile or runaway file must not be able to
produce an unbounded answer. The ceiling at the very end is the last line of defence, not the plan.

**2. Always say what you left out.** `8000 match(es); showing oldest 3 (7997 more not shown - narrow the query,
raise max_matches, or use newest_first)`. A silently truncated answer is worse than none:
the agent concludes the three it saw are all there is. The count costs nothing, since we scan the file
anyway, and the message tells the agent its options.

**3. Choose which end to keep.** For incidents the newest matches matter. `newest_first` uses a ring
buffer (`deque(maxlen=N)`): scan forward, drop the oldest, memory O(N). Streaming and "last N" are not in
conflict.

**4. Do not read what was not asked about.** A time window on a 600 MB file should not cost 600 MB of I/O.
Logs are sorted by time, so binary search works on **bytes**:

```
 probe middle byte -> skip partial line -> read first timestamp
   too early? search the right half.  too late? the left half.
 stop when the bracket is 64 KiB, back off one window, scan forward
```

`bisect_offset` needs ~13 probes for 600 MB. The demo log (400,000 lines) examines 1,905 lines instead of
400,000. Then `lines_between` stops once timestamps pass `until` plus a slack, because "sorted" really
means "roughly sorted" (services buffer, clocks skew). Pick the slack from what you can tolerate, and
state the assumption in the docs.

## Errors are part of the output

Notice every failure in Module 07 says what to do next ("start the server with --dir", "use
YYYY-MM-DD HH:MM:SS"). The agent cannot ask a human what `ValueError: bad time` meant.

## Run it

```bash
python main.py
```

## What the real server measured

On a 601 MiB, 7.3M-line file: a full scan of every line takes 20-30 s; the same search with a one-minute
window and bisection takes 0.5 s. Peak process memory is 25.5 MiB in both cases.
