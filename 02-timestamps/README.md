# Module 02: Timestamps

## The Concept

Every useful log question has a time in it: "since 02:00", "in the last hour", "which request came
first, the gateway's or billing's?" To answer them you need one number per event, comparable across
files, services and time zones: **UTC epoch seconds**.

Logs make this hard in five ways. `main.py` handles each:

| Problem | Example | Solution |
|---------|---------|----------|
| Many shapes | `2026-11-06 12:30:00,250`, `06/Nov/2026:14:30:00 +0200`, `Nov  6 12:30:00`, `"ts":1730000000123` | One small regex per family, run on bytes |
| Zones | `Z`, `+02:00`, `-0500`, or nothing | A zone *on the line* always wins; otherwise use an explicit assumed zone |
| No year | syslog | Use the file's modification time: an entry cannot be newer than the last write |
| Epoch units | seconds, ms, µs | Magnitude tells you: above 1e14 is µs, above 1e11 is ms |
| Speed | millions of lines | Cache the calendar math: consecutive lines share a second |

## The assumed zone is a parameter, not a secret

A naive timestamp (`2026-11-06 12:30:00`) has no zone. Every tool must pick one, and the honest
design is to make it an argument (`tz="+03:00"`) that the agent can set and see echoed back in
the output ("times in UTC+03:00"). Silently guessing UTC is how a 3-hour error ends up in an
incident report.

## Anchoring decides what counts as an event

The ISO regex only allows up to three non-word characters before the timestamp (`^\W{0,3}`), so
`[2026-11-06 ...` matches but `    at Foo(Foo.java) 2026-11-06...` does not. That anchor is the
whole basis of multi-line grouping in Module 04: a line **starts an event** if and only if it has a
timestamp where a timestamp belongs.

## The syslog year trick

`Dec 31 23:59:59` plus a file last written on 2027-01-02: try 2027 first (Dec 31, 2027 is in the
future relative to the file, rejected), then 2026 (accepted). A one-day tolerance covers clock skew.
It is a heuristic and fails when a file is touched long after it was written (restored backups,
`touch`): the guessed year can be wrong, and nothing in the line can correct it.

## Run it

```bash
python main.py
```

The assertions include the property that matters most for tracing: the same instant written in
three zones (`10:00Z`, `12:00+02:00`, `05:00-0500`) parses to the same number.
