# Break It: Multi-Line Events

## Challenge 1: A Timestamp Inside a Trace

Add the line `    retrying at 2026-11-06 10:00:02 after backoff` (indented) in the middle of the Python trace
in `LOG`. Does the event count change? Then try the same line with no indentation.

**Hint:** `ISO_AT` allows only up to three non-word characters before the date, so the indented
line is still a continuation. Unindented, it splits the trace. Anchoring is the whole defence.

## Challenge 2: Drop the Tail

Delete the `self.tail = line` branch and run the `giant` test. What is the last line you have now,
and what would the Module 05 template for this event be?

**Hint:** The kept lines end at `at frame199`, so the template loses its exception and unrelated
failures collapse into one cluster.

## Challenge 3: Grouping Without Bounds

Make `add` append every line. Feed a generator that produces an endless trace and watch memory.

**Hint:** An event is the one place this design holds data proportional to the input, so it needs its
own cap.
