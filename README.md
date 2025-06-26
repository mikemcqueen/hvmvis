This displays the terms in Node memory for a branch of HVM3-Strict running bench_parallel_sum_range.hvms with a @Height of 2.

HVM3 is not actually executed or required for this - I generated a logfile of all HVM3 memory operations and included
it in this repo. This viewer parses that log file.

Terms start as the values they are initialized to in expand_ref(), or in the case of MATU32 "emergent nodes", the values
they are initialized to during execution of that interaction, and they update as each memory operation of each subsequent
interaction is executed.

When a term's color changes to orange, it's never accessed again (i.e. it has effectively become a "free node").

I (with AI assistance) wrote this primarily to try to gain some insight/intuition about how and when node space becomes free.

Requires Python3 12.x (12.3.2 known to work)

Requires pygame 2.x (2.5.2 known to work). Latest as of June 2025. pip install pygame works i think.

Usage:

python3 parse.py memlog/memlog.2
