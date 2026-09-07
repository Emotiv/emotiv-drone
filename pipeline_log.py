"""One place that answers "is the pipeline working, and if not, where did it stop".

Three streams come out of Cortex and turn into two outputs. mot becomes the
drone's heading, com becomes forward motion, dev is the contact quality behind
both. When the demo misbehaves the question is always which of those five
things stopped, and until now the log could not say: a stream that simply
stops arriving produces no lines at all, which reads exactly like a stream
that is arriving and doing nothing.

So this tracks each stream's arrival rate rather than its contents, and prints
one heartbeat carrying every stage at once. A rate is the thing that
distinguishes the failures: 0 Hz is a dead stream, a rate well under the
expected one is a struggling link, and the expected rate with no movement is a
problem further down in the maths.
"""

import time


class StreamStat:
    """Arrival rate and liveness for one Cortex stream."""

    # Long enough that a stream which merely stutters is not called dead --
    # com in particular is event driven and legitimately sparse.
    STALL_AFTER = 3.0

    def __init__(self, name: str):
        self.name = name
        self.total = 0
        self.first_at = None
        self.last_at = None
        self._window = 0
        self._window_start = None
        self.stalled = False

    def mark(self) -> str:
        """Record one sample. Returns a line to log, or ''."""
        now = time.time()
        self.total += 1
        self.last_at = now
        if self._window_start is None:
            self._window_start = now
        self._window += 1

        if self.first_at is None:
            self.first_at = now
            return f"[stream] {self.name} first sample"
        if self.stalled:
            self.stalled = False
            return f"[stream] {self.name} resumed"
        return ""

    def check_stall(self) -> str:
        """Returns a line if the stream has just gone quiet, else ''."""
        if self.first_at is None or self.stalled or self.last_at is None:
            return ""
        gap = time.time() - self.last_at
        if gap > self.STALL_AFTER:
            self.stalled = True
            return (f"[stream] {self.name} STALLED - nothing for {gap:.1f}s "
                    f"after {self.total} samples")
        return ""

    def rate(self) -> float:
        """Samples per second since the last read, then reset."""
        if self._window_start is None:
            return 0.0
        span = time.time() - self._window_start
        hz = self._window / span if span > 0 else 0.0
        self._window = 0
        self._window_start = time.time()
        return hz
