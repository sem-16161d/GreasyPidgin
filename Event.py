from musicscore.chord import Chord

class Event:
    def __init__(
        self,
        startTimeSec: float = 0.0,
        durationSec: float = 1.0,
        dynamicdB: float = 0.0,
        pitchesMidi=60,
        bpm=120
    ):
        self.startTimeSec = startTimeSec
        self.durationSec = durationSec
        self.endTimeSec = startTimeSec + durationSec

        self.dynamicdB = dynamicdB
        self.bpm = bpm

        self.startTimeBeats = round(startTimeSec * bpm / 60, 5)
        self.quarterDurationFloat = round(durationSec * bpm / 60, 5)
        self.endTimeBeats = round(self.endTimeSec * bpm / 60, 5)

        # the actual musicscore chord
        self.chord = Chord(midis=pitchesMidi,
                           quarter_duration=self.quarterDurationFloat)

    def add_tie(self, tie_type: str):
        self.chord.add_tie(tie_type)


    def dump(self):
        print(
            f"startTimeBeats: {self.startTimeBeats}, "
            f"quarter_duration: {self.quarterDurationFloat}, "
            f"dynamicdB: {self.dynamicdB}, "
            f"pitchesMidi: {[m.value for m in self.chord.midis]},"
        )