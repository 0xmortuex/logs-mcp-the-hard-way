# Module 07: The MCP Wrapper and Testing

## The Concept

You now have a streaming, format-aware, clustering engine. Wrapping it in MCP is the smallest part,
and the part where most servers lose their users:

1. **Tool descriptions are the product.** The model reads the name, the docstring and the argument
   schema, nothing else, to decide what to call. `log_overview`'s docstring says "Start here." That
   one phrase changes which tool agents call first. The server-level `instructions` give the order:
   overview, clusters, timeline, search.
2. **Few tools, each a question.** Seven tools map to seven questions an engineer asks in an incident
   (what is this? what is failing? when? exactly which events? which request? what changed?
   what is happening now?). One mega-tool with 20 options would be unusable.
3. **Errors are messages.** With `mcp>=2`, only a `ToolError`'s text reaches the client; any other
   exception becomes `Error executing tool X`. So the `tool` decorator converts *expected* failures
   (`ToolFailure`, `OSError`, `ValueError`, `re.error`) into `ToolError` and lets real bugs stay
   loud in the server's log. Never swallow, never fall back silently.
4. **The sandbox is the security model.** `resolve()` calls `os.path.realpath` **before** the
   prefix check, so `../` and symlinks cannot escape, and compares with `normcase`, because
   `C:\Logs` and `c:\logs` are the same directory on Windows. The check includes the separator
   (`root + os.sep`), otherwise `/logs-secret` passes as being "inside" `/logs`.
5. **Never print to stdout in serve mode.** stdout is the JSON-RPC channel.

## Testing: real client, real server, real file

`main.py` run without flags is the test. It:

- writes a log with a planted story (a steady DB-timeout error, then a new "payment gateway down"
  failure with a Python-style exception line in the last 3 minutes),
- launches **itself** as a subprocess with `--serve --dir <tmp>`,
- connects with the SDK's real stdio client and calls all seven tools,
- asserts on content (the clusters show `<n>` templates; `compare_windows` finds the new one;
  the cap notice is present; the sandbox rejects `../secret.log`),
- and checks that the *error messages* arrive intact.

A unit test of `template()` cannot catch a registration bug, a stdout print, or a ToolError that
turned into a generic message. The process boundary can.

## Differences from the real server

This is the same engine, simplified: ISO-timestamped text only, UTC only, no globs or rotation, no
sampling for huge files, no bisection (Module 06 shows it separately). The real server (`logs-mcp`)
adds those, plus a 45-test suite and a benchmark.

## Run it

```bash
python main.py
```

To use it from a client: `python main.py --serve --dir /var/log/myapp`.
