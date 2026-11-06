# Module 05: Clustering by Templating

## The Concept

12,000 error lines are not 12,000 problems. They are usually five problems with different numbers
in them:

```
timeout after 3204ms to 10.0.0.5:5432
timeout after 3511ms to 10.0.0.9:5432     ->   timeout after <n>ms to <ip>      x 4000
```

Replace the variable parts with placeholders and group by the result. The template is the
identity of the problem; the count says how big it is; first/last seen say when.

## Why not machine learning

Log-parsing research (Drain and friends) learns templates. That needs state, tuning and a
dependency, and the output can shift between runs. Regex normalisation is deterministic, explainable
("numbers, UUIDs, IPs, hex ids, paths, URLs") and fast enough to run on millions of events. Its cost
is honest: an id shape you did not think of creates extra templates. The README's limits section
says so.

## Rule order is the algorithm

`RULES` run top to bottom and **order matters**:

- UUID before anything: otherwise the number rule shreds it into `<n>-<n>-<n>`.
- Timestamps before numbers, IPs before numbers, URLs before paths.
- Long hex ids (8+ chars) become `<hex>` even when they are all digits. `req=42472479` and
  `req=c541013d` must land in the same cluster. (The real server first treated them differently, which
  split one problem into two clusters.)
- Mixed letters-and-digits tokens (`user8f2c1`) become `<id>`, **except** `3204ms`: a number with a
  unit is still a number. A negative lookahead protects it.

## Exceptions identify bugs

Two different failures can log `charge failed order=7`. The difference is at the bottom of the trace:
`KeyError: 'sku'` vs `ValueError: bad sku 12`. So `template()` appends ` || ` plus the normalised
exception line for multi-line events. Only unindented lines count, since `File "x.py", line 9`
is context, not a cause.

## Strip the prefix

Timestamp and level are removed from the template, or the same message at ERROR and FATAL would be
two clusters, and no two lines would ever share a timestamp anyway.

## Cap the dictionary

A log with a random token you failed to normalise produces one template per line: an unbounded
dict, which is a memory leak with a nice name. `cluster()` stops adding at `max_templates`, keeps
counting existing ones, and returns the overflow count. The tool prints "N events were not grouped."
The agent is told, not misled.

## Run it

```bash
python main.py
```
