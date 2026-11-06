# Break It: Timestamps

## Challenge 1: Ignore the Zone on the Line

In `Parser.iso`, always subtract `self.assume_tz` instead of `tz_seconds(m.group(3), ...)`. Which
assertions fail? Think about what this does to two services that log in different zones.

**Hint:** Merging a UTC gateway log with a `+02:00` billing log would interleave events two hours
out of order, and a request trace would read backwards.

## Challenge 2: Year-Less Dates at New Year

Change the syslog rule to always use `mtime_year`. Parse `Dec 31 23:59:59` from a file last written
on January 2nd.

**Hint:** You get a date 364 days in the future. Everything in December looks newer than the end
of the log, so "last 30 minutes" windows come back empty.

## Challenge 3: A Millisecond Epoch Treated as Seconds

Delete the magnitude check in `keyed`. What year does `1730000000123` land in?

**Hint:** Roughly the year 56,000. It is a perfectly valid float, so nothing raises, and every window
filter quietly returns nothing.
