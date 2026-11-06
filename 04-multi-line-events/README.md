# Module 04: Multi-Line Events

## The Concept

A stack trace is one event. If your tool treats each physical line as a record, three things go
wrong at once: a search for `KeyError` finds line 7 of a trace with no clue *which request* failed,
the ERROR line and its trace get counted as 5 events, and a `tail` cuts a trace in half.

The fix is one rule that needs no knowledge of Python, Java, Go or Rust traces:

> A line that **starts with a timestamp** begins a new event. Every other line belongs to the
> previous one.

That is `events()` in `main.py`: a generator holding exactly one event at a time. Memory stays flat
however long the file is.

## Bound the event, remember the end

Some services print a 40,000-line trace in a loop. `Event.add` keeps at most 200 lines but counts
all of them, and always remembers the **last** line in `tail`. The last line of a Python trace is the
exception; in Java it is often the root `Caused by:`. Module 05 clusters on it, so the cap must
never throw it away.

## Files without timestamps

If nothing has a timestamp, "starts with a timestamp" would call every line a continuation. So
the grouping rule is pluggable: `starts_event` can be `indent_or_marker`, which treats indented
lines and known markers (`Caused by`, `Traceback`, `... 3 more`) as continuations. The real server
picks the rule per file from format detection.

## Details that matter

- Junk before the first timestamp (a banner) becomes its own event; nothing is dropped.
- Keep the **starting line number**. Search results say `app.log:2`, and for the agent that is the
  cheapest way to ask for context later.
- The consumer sees the whole event. A match on `ConnectionReset` prints the `charge failed order=7`
  head line with it. That is the point.

## Run it

```bash
python main.py
```
