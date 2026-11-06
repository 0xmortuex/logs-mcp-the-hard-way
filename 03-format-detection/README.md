# Module 03: Format Detection

## The Concept

The agent says "look at `/var/log/app/`". It does not say what is in there. The server must work
out whether each file is JSON lines, logfmt, syslog, an nginx access log or free text with ISO
timestamps, because the format decides how to find the timestamp and the level.

Do not parse the first line and hope. First lines are banners (`=== starting v2 ===`), blank, or a
stack trace from before rotation. Instead **sample and vote**:

1. Read the first few hundred lines.
2. Throw away indented lines (stack traces) and blanks.
3. Each remaining line votes for the *first* format it fits.
4. A format wins with at least half the votes; otherwise the file is `plain`.

## Order of tests matters

An nginx access line contains a date, so it also "looks ISO-ish" in loose regexes. Test the
more specific formats first (JSON, access log, syslog), the loosest (logfmt) last. If two formats can
match the same line, the order *is* the specification. The tests in `main.py` pin it.

## Levels are a separate problem

- JSON and logfmt carry an explicit key (`"level":"error"`, `lvl=warn`). Trust the key over any bare
  word in the message: `level=warn msg="ERROR in text"` is a warning.
- Plain text uses bare uppercase words (`ERROR`, `WARNING`) or `[error]` (nginx error log).
  Only **uppercase** words are matched, because lowercase prose says "error handled" all the time.
- Numbers happen: pino logs levels as 10 to 60.
- Access logs have no level at all. Derive one from the HTTP status: 5xx is an error, 4xx a warning.
  Without that, "show me the errors" would be empty on the most common server log in existence.
- Only the first ~240 bytes are searched, since messages quote other log lines.

## Multi-line style

A second, independent question: do events span lines? `Traceback (most recent call last)` means
Python; indented `at ...` lines mean Java. The overview tool reports this, but Module 04's grouping
rule does not need it to work.

## Run it

```bash
python main.py
```
