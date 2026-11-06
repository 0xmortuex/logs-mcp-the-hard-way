# MCP Log Server — The Hard Way

Build an MCP server that lets an AI agent investigate log files far too big to read. Start from
"how do I read the last 20 lines of a 2 GB file" and end with an agent that finds the error that
started an hour ago, groups it with its siblings, and follows the request that caused it. Standard
library plus the `mcp` SDK, and every line explained.

At the end you will have built a minimal [logs-mcp](https://github.com/0xmortuex/logs-mcp)
yourself, and you will understand the parts most tutorials skip: **streaming at constant
memory**, **trusting timestamps**, and **designing tool output for a reader with a context window**.

## Why This Exists

Most log tools are built for humans scrolling. An agent needs the opposite: small, bounded,
honest answers about files it will never read.

- the file may be bigger than memory
- timestamps come in six formats and a dozen time zones
- an "event" is often twenty lines (a stack trace), not one
- 12,000 errors are usually five problems
- an answer that silently drops results is worse than no answer

## Who This Is For

- Developers who built a "hello world" MCP server and want a real one
- SREs and backend engineers who want an agent in their incident loop
- Anyone curious how `tail`, `grep` and log aggregators actually work

**Prerequisites:** Python. Nothing else; the modules generate their own logs.
`pip install -r requirements.txt` (only `mcp` and `anyio`).

## Modules

| # | Module | What You'll Build |
|---|--------|-------------------|
| 01 | [Streaming and Reading Backwards](01-streaming-and-reading-backwards/) | Constant-memory forward scans, gzip behind one API, a block-wise reverse reader and its boundary bugs |
| 02 | [Timestamps](02-timestamps/) | ISO, access-log, syslog (no year!) and JSON/epoch timestamps normalised to UTC |
| 03 | [Format Detection](03-format-detection/) | Voting over a sample to choose a format; finding levels without false alarms |
| 04 | [Multi-Line Events](04-multi-line-events/) | One rule that glues stack traces to the event that caused them, with bounded memory |
| 05 | [Clustering by Templating](05-clustering-by-templating/) | Regex normalisation that turns 12,000 errors into five templates |
| 06 | [Caps and Output Design](06-caps-and-output-design/) | Hard caps, honest "N more" notices, ring buffers, and byte-level bisection |
| 07 | [The MCP Wrapper and Testing](07-the-mcp-wrapper-and-testing/) | All seven tools behind a sandboxed MCP server, tested over a real stdio session |

Each module contains:
- **`README.md`**: the concepts and design decisions
- **`main.py`**: a working implementation that stands alone and checks itself with `assert`
- **`break-it.md`**: challenges that break your own code, with hints

## How To Use This Course

**Option A: Build along.** Read the modules in order, run each `main.py`, then do the break-it challenges.

**Option B: Reference.** Each `main.py` stands alone, with no imports between modules.

**Option C: Use the finished tool.** `pip install logs-mcp` is what these modules grow into.

## Every Module Is Verified

```bash
python verify.py            # all seven
python verify.py 02 05      # some
```

This runs each `main.py` in a fresh interpreter and fails unless it exits 0 and prints its
"module NN ok" line. Module 07 launches its own server and talks to it over real stdio. CI runs
it on Linux, macOS and Windows on every push and weekly.

## Architecture Overview

```
 AI agent (Claude Code, ...)
        |  MCP over stdio: JSON-RPC tool calls              <- Module 07
        v
 +------------------------------------------------------+
 | tools: overview / search / clusters / timeline /     |   <- Module 06 (caps, notices)
 |        tail / trace / compare_windows                |
 |   +-- clustering: normalise -> template -> count     |   <- Module 05
 |   +-- events: timestamp starts one, rest glue on     |   <- Module 04
 |   +-- format + level detection by voting             |   <- Module 03
 |   +-- timestamps -> UTC epoch                        |   <- Module 02
 |   +-- streaming bytes, forward / backward / gzip     |   <- Module 01
 +------------------------------------------------------+
        |
        v
   log files on disk (plain, .gz, rotated)  -- never loaded into memory
```

## Key Design Principles

**1. Stream or die.** If any code path holds memory proportional to the file, the first big file
finds it. Test with a measurement, not a hope.

**2. Say what you left out.** Every cap comes with a count and a next step.

**3. A line is not an event.** Group first, then count, search and cluster.

**4. Guess out loud.** Assumed time zones, inferred years and "roughly chronological" are
parameters or documented limits, never silent.

## Tech Stack

- **Language:** Python 3.10+
- **Protocol:** MCP over stdio
- **Dependencies:** `mcp`, `anyio`, nothing else

## License

MIT. Use it, modify it, ship it.

---

Built by [0xmortuex](https://github.com/0xmortuex)
