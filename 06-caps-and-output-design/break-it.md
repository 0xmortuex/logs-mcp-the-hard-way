# Break It: Caps and Output

## Challenge 1: Forget the Count

Change `search` to stop reading after `max_matches` matches (break out of the loop). Compare the
header with the original.

**Hint:** It is faster, and now it cannot say how many more there are. Decide which you want, and note
that the real server chose exact counts and put "narrow the window" first in its advice.

## Challenge 2: Slack Zero

Call `lines_between` with `slack=0` on a log where two lines are out of order (swap lines 200,010 and
200,011 in the file). What happens at the boundary?

**Hint:** Early stop fires at the first line past `until`, so the straggler just after it is missed.
Slack trades speed for tolerance of disorder.

## Challenge 3: Bisect an Unsorted File

Shuffle the file's lines and run `bisect_offset`. Does it fail loudly?

**Hint:** No. It returns a plausible offset and `lines_between` returns wrong results without an error.
The real server does not detect it either; it documents the "roughly chronological" assumption.
Think about whether yours should check, for example by comparing the first and last timestamps.
