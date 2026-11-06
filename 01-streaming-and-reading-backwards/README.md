# Module 01: Streaming and Reading Backwards

## The Concept

A production log can be 2 GB. Your agent's context window is a few hundred thousand tokens and
your server may run on a laptop. Whatever you build has to work on files that do not fit in
memory, and it has to stay fast when the question is "what happened a second ago?"

Two ideas cover almost everything:

1. **Stream forward.** Iterate the file one line at a time. Memory is the size of one line (plus an
   I/O buffer), whatever the file size. `main.py` measures it: a 16 MB file costs ~1 MB to scan
   and ~39 MB to `read().splitlines()`. Scale that to 2 GB.
2. **Read backwards for the end.** `tail` should not read 2 GB to show 20 lines. Seek to the end and
   read blocks towards the start until you have enough lines.

## Work in bytes

`main.py` opens files in binary mode and never decodes until it prints. Decoding millions of
lines to `str` just to look at the first 30 characters is the biggest avoidable cost, and it
also means one invalid UTF-8 byte in a log cannot crash a scan (decode with `errors="replace"`
at the edge).

## Compressed and rotated files

`open_stream` sniffs the first two bytes (`1f 8b`) instead of trusting the name: rotation tools
rename files (`app.log.1.gz` today, `app.log.1` after someone decompresses it). A gzip file
streams forward at the same API but **cannot be read backwards cheaply**, so any tail of a `.gz`
means scanning from the start. The real server reflects that in its tool docs.

## Reading backwards: the block-boundary problem

Read 64 KiB from the end, `split(b"\n")`, and you have a problem: the first piece is almost
certainly the *end* of a line whose start is in the previous (earlier) block. So:

```
 file:   ...[ line A ][ line B ][ line C ][ line D ]
 blocks:      |__ block 1 __|____ block 2 ____|
 split block 2 ->  ["ine B", "line C", "line D", ""]
                     ^ carry this into block 1, where it becomes the tail of "line B"
```

The code carries `parts[0]` into the next read. Two details that bite:

- A file that ends with `\n` splits into a final empty string. That is not a line. Skip it exactly
  once, at the very end (`first`). The real server had this bug in its first test run: `tail -n 3`
  returned two lines.
- `\r\n` files: strip the `\r` after splitting on `\n`.

## Run it

```bash
python main.py
```

It checks the backwards reader against the forward reader at block sizes 7, 100, 4096 and 65536
(tiny blocks force a carry on nearly every line) and against five edge-case files.

## What the real server does

`files.py` in logs-mcp has the same `reverse_lines`, plus `count_lines` (newlines counted in 1 MiB
blocks: exact line counts without iterating lines). `tail_logs` uses the reverse reader, and so
does finding a file's *last* timestamp, which is how `-30m` can mean "30 minutes before the newest
entry" without scanning the file.
