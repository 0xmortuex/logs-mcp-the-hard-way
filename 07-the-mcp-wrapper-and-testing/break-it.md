# Break It: The Wrapper

## Challenge 1: Print to Stdout

Add `print("scanning", path)` at the top of `log_overview` and run `main.py`. What fails?

**Hint:** In `--serve` mode stdout carries JSON-RPC, so the stray line corrupts the stream. Depending
on the SDK version the client skips it, errors on it, or hangs. Use `file=sys.stderr`.

## Challenge 2: A Sloppy Sandbox

In `resolve`, replace `os.path.normcase(r) + os.sep` with just `os.path.normcase(r)`, then ask for a
sibling directory whose name starts with the allowed one (`logs` vs `logs-private`).

**Hint:** `startswith("/data/logs")` is true for `/data/logs-private/x.log`. Add the separator.
Also try removing `realpath` and create a symlink inside the allowed directory that points outside.

## Challenge 3: Let a Real Exception Through

In the `tool` decorator, catch `Exception` instead of the expected list. Make `events()` raise an
`AttributeError` (a typo), and call a tool.

**Hint:** The agent now receives the raw Python message as if it were advice, and a genuine bug
looks like a user error. Keep the expected list narrow so bugs fail loudly where you can see them.
