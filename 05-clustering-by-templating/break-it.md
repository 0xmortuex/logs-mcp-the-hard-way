# Break It: Clustering

## Challenge 1: Numbers First

Move the `<n>` rule to the top of `RULES`. Which assertions fail, and what does a UUID look like now?

**Hint:** `8f14e45f-ceea-467a-...` becomes `<n>f<n>e<n>f-ceea-...` fragments, or half-replaced tokens.
Greedy catch-all rules must go last.

## Challenge 2: Find an Id That Escapes

Write three realistic log lines with ids the rules do not normalise (try base64 tokens like
`dGVzdA==`, or ids such as `ORD-2026-0042`). How many templates do 100 such lines create?

**Hint:** Each unique unmatched token makes its own cluster. Add a rule for your shape, or accept
the overflow cap. Both are legitimate; hiding it is not.

## Challenge 3: Cluster Without the Exception

In `template`, delete the exception suffix. Run the `c1`/`c2` check.

**Hint:** Two bugs now share one template, and the larger one hides the smaller. Check the example
event the tool prints: it comes from whichever bug logged first.
