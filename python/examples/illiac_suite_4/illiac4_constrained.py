"""
Illiac Suite, 4th movement -- with the paper's rules (section 5, first experiment):
every eighth-note chord is a major or minor triad (any inversion), no parallel
unisons/octaves/fifths between neighbouring voices or the outer voices, and
Violin I preferably above Violin II.

    python illiac4_constrained.py [seed]

The Markov chain proposes the four voices' steps; a proposal that breaks a rule is
thrown away and drawn again (MAX_TRIES). If nothing fits, all voices hold their pitch.
Writes out/illiac4_constrained.mid and .musicxml next to this file.
"""
import itertools
import random
import sys
from pathlib import Path

from illiac_common import (EIGHTHS_PER_TABLE, INTERVAL_ORDER, VOICES, advance,
                           anyParallel, isTriad, makeChain, stageOf, writeScore)

MAX_TRIES = 2000


def startChord():
    chords = [c for c in itertools.product(*(domain for _, domain, _ in VOICES))
              if isTriad(c) and c[0] >= c[1]]
    return random.choice(chords)


def compose(seed=None):
    """Returns (pitches per voice, number of eighths where nothing fit and all voices held)."""
    random.seed(seed)
    pitches = [[p] for p in startChord()]
    prev = [0] * len(VOICES)
    holds = 0
    chains = [makeChain(s) for s in range(len(INTERVAL_ORDER))]
    for i in range(1, len(INTERVAL_ORDER) * EIGHTHS_PER_TABLE + 1):
        now = [p[-1] for p in pitches]
        for attempt in range(MAX_TRIES):
            steps = [advance(chains[stageOf(i)], prev[v], now[v], low, high)
                     for v, (_, _, (low, high)) in enumerate(VOICES)]
            new = [p + s for p, s in zip(now, steps)]
            # the voice-crossing preference is dropped for the second half of the tries
            if isTriad(new) and not anyParallel(now, new) and (new[0] >= new[1] or attempt >= MAX_TRIES // 2):
                break
        else:
            steps, new, holds = [0] * len(VOICES), now, holds + 1
        for v in range(len(VOICES)):
            prev[v] = steps[v]
            pitches[v].append(new[v])
    return pitches, holds


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
    pitches, holds = compose(seed)
    print(f"{holds} of {len(pitches[0]) - 1} eighths: no proposal fit, all voices held")
    out = Path(__file__).with_name("out") / "illiac4_constrained"
    writeScore(pitches, str(out), "Illiac Suite, 4th movement (with the paper's rules)")
