"""
Illiac Suite, 4th movement -- original idea: four independent voices, no harmony rules.

    python illiac4_original.py [seed]

Writes out/illiac4_original.mid and .musicxml next to this file.
"""
import random
import sys
from pathlib import Path

from illiac_common import (EIGHTHS_PER_TABLE, INTERVAL_ORDER, VOICES, advance,
                           makeChain, stageOf, writeScore)


def compose(seed=None):
    random.seed(seed)
    pitches = [[random.choice(domain)] for _, domain, _ in VOICES]
    prev = [0] * len(VOICES)
    chains = [makeChain(s) for s in range(len(INTERVAL_ORDER))]
    for i in range(1, len(INTERVAL_ORDER) * EIGHTHS_PER_TABLE + 1):
        for v, (_, _, (low, high)) in enumerate(VOICES):
            prev[v] = advance(chains[stageOf(i)], prev[v], pitches[v][-1], low, high)
            pitches[v].append(pitches[v][-1] + prev[v])
    return pitches


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
    out = Path(__file__).with_name("out") / "illiac4_original"
    writeScore(compose(seed), str(out), "Illiac Suite, 4th movement (original idea)")
