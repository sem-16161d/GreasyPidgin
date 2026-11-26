"""
Illiac Suite, 4th movement -- parts shared by the two versions.

Source: Sandred, Laurson & Kuuskankare, "Revisiting the Illiac Suite - a rule
based approach to stochastic processes", sections 2.1 and 5.

Taken from the paper:
  * four voices, steady eighth-note pulse in 6/8; only the pitches are chosen
  * one table of melodic-interval probabilities per voice, valid for 2 measures
    (12 eighths), then replaced by the next table. Here a table governs the
    intervals leading INTO those 12 notes, so the first pitch is sustained for
    exactly the first 2 bars
  * the first table allows only the unison; every next table adds one interval,
    in the order of INTERVAL_ORDER below
  * simpler intervals always get a higher probability
  * a repeated pitch is tied into one longer note
  * start pitches come from the domains in the paper's Fig. 1 (as read there)

Not in the paper, so invented here (marked "choice:"): the probability values,
how the previous interval changes the next one (Hiller only says it did), the
voice ranges, the tempo, the length of the movement and the final bar.
"""
import os
import tempfile

import mido

from GreasyPidgin import Gesture, MarkovChain, MarkovRule, MarkovRules

BPM = 96                  # choice: quarter note = 96
TIME_SIGNATURE = "6/8"
EIGHTH = 0.5              # in quarter-note beats
EIGHTHS_PER_TABLE = 12    # 2 measures of 6/8
FINAL_EIGHTHS = 6         # choice: last note fills one whole bar

# semitones, in the order the paper adds them: unison, octave, fifth, fourth,
# major third, minor sixth, minor third, major sixth, major second,
# minor seventh, minor second, major seventh, tritone
INTERVAL_ORDER = [0, 12, 7, 5, 4, 8, 3, 9, 2, 10, 1, 11, 6]

# name, start-pitch domain (paper Fig. 1), range (choice)
VOICES = [
    ("Violin I",    range(55, 62), (55, 91)),
    ("Violin II",   range(55, 62), (55, 91)),
    ("Viola",       range(48, 55), (48, 81)),
    ("Violoncello", range(36, 43), (36, 69)),
]


def stageOf(noteIndex):
    """Table number for the interval leading into note `noteIndex` (the last table repeats for the final note)."""
    return min(noteIndex // EIGHTHS_PER_TABLE, len(INTERVAL_ORDER) - 1)


def makeChain(stage):
    """Order-1 MarkovChain over signed melodic steps; the state is the previous step."""
    active = INTERVAL_ORDER[:stage + 1]
    base = {}
    for rank, interval in enumerate(active):
        steps = (0,) if interval == 0 else (interval, -interval)
        for step in steps:
            base[step] = (len(active) - rank) / len(steps)   # choice: linear fall-off with rank
    rules = []
    for prev in base:
        weights = dict(base)
        if prev == 0:
            weights[0] *= 2                                  # choice: a sustained note tends to stay sustained
        if abs(prev) >= 5:
            for step in weights:
                if step * prev > 0:
                    weights[step] *= 0.25                    # choice: after a leap, don't keep going the same way
        rules.append(MarkovRule(prev, list(weights), list(weights.values())))
    return MarkovChain(rules=MarkovRules(rules))


def advance(chain, prevStep, pitch, low, high):
    """One Markov step; a step that leaves the voice's range is drawn again (choice)."""
    for _ in range(50):
        step = chain.nextElement(prevStep)
        if low <= pitch + step <= high:
            return step
    return 0


def isTriad(pitches):
    """True if the pitch classes are exactly a major or minor triad (any inversion, any doubling)."""
    pcs = {p % 12 for p in pitches}
    return any(pcs == {r, (r + 4) % 12, (r + 7) % 12} or pcs == {r, (r + 3) % 12, (r + 7) % 12}
               for r in range(12))


def parallelPerfect(lower0, lower1, upper0, upper1):
    """Both voices move the same way and keep the same unison/octave/fifth."""
    if lower0 == lower1 or upper0 == upper1 or (lower1 > lower0) != (upper1 > upper0):
        return False
    first, second = (upper0 - lower0) % 12, (upper1 - lower1) % 12
    return first == second and first in (0, 7)


def anyParallel(now, new):
    """Neighbouring voices and the outer voices, as in the paper."""
    pairs = [(0, 1), (1, 2), (2, 3), (0, 3)]
    return any(parallelPerfect(now[lo], new[lo], now[up], new[up]) for up, lo in pairs)


# ---------------------------------------------------------------- export

def _gesture(pitches, velocities):
    """Tie repeated pitches into one note, then build a Gesture (one note per Phonon)."""
    notes = []   # [pitch, eighths, velocity at onset]
    for pitch, velocity in zip(pitches, velocities):
        if notes and notes[-1][0] == pitch:
            notes[-1][1] += 1
        else:
            notes.append([pitch, 1, velocity])
    notes[-1][1] = FINAL_EIGHTHS
    durations = [eighths * EIGHTH for _, eighths, _ in notes]
    return Gesture.fromLists(
        len(notes),
        startDeltas=[0.0] + durations[:-1],   # time from the previous onset; first note sits at 0
        durations=durations,
        pitches=[p for p, _, _ in notes],
        dynamics=[v for _, _, v in notes],
        timeUnit="b", bpm=BPM,
    )


def writeScore(voices, stem, title):
    """voices: four pitch lists (one pitch per eighth). Writes <stem>.mid and <stem>.musicxml."""
    os.makedirs(os.path.dirname(stem) or ".", exist_ok=True)
    total = len(voices[0])
    velocities = [round(25 + 85 * i / (total - 1)) for i in range(total)]   # choice: pp -> ff over the movement
    gestures = [_gesture(v, velocities) for v in voices]

    # The exporters hand out tracks/parts greedily, not per voice, so every voice is
    # exported alone and the files are merged afterwards.
    with tempfile.TemporaryDirectory() as tmp:
        midi = mido.MidiFile(ticks_per_beat=480)
        xmlFiles = []
        for i, (g, (name, _, _)) in enumerate(zip(gestures, VOICES)):
            g.toMidi(f"{tmp}/{i}.mid", channel=i, trackName=name, bpm=BPM)
            midi.tracks.append(mido.MidiFile(f"{tmp}/{i}.mid").tracks[0])
            xmlFiles.append(f"{tmp}/{i}.musicxml")
        midi.save(f"{stem}.mid")

        try:
            import music21 as m21
        except ImportError:
            print("music21 not installed: skipped MusicXML (pip install music21)")
            return
        for g, path in zip(gestures, xmlFiles):
            g.toXml(path, timeSignature=TIME_SIGNATURE)
        score = m21.stream.Score()
        score.metadata = m21.metadata.Metadata(title=title)
        clefs = [m21.clef.TrebleClef, m21.clef.TrebleClef, m21.clef.AltoClef, m21.clef.BassClef]
        for i, (path, (name, _, _), clef) in enumerate(zip(xmlFiles, VOICES, clefs)):
            part = m21.converter.parse(path).parts[0]
            part.partName = name
            first, last = part.getElementsByClass("Measure")[0], part.getElementsByClass("Measure")[-1]
            first.insert(0, clef())
            first.insert(0, m21.dynamics.Dynamic("pp"))
            last.insert(0, m21.dynamics.Dynamic("ff"))
            if i == 0:
                first.insert(0, m21.expressions.TextExpression("crescendo poco a poco"))
            score.insert(0, part)
        score.write("musicxml", fp=f"{stem}.musicxml")
