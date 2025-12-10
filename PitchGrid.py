import math

class PitchGrid:
    def __init__(
        self,
        stepsPerOctave=12,
        refFreq=443.0,
        refMidi=69,
        midiMin=0,
        midiMax=130
    ):
        self.stepsPerOctave = stepsPerOctave
        self.smallestMicrotone = 12 / stepsPerOctave
        self.refFreq = refFreq
        self.refMidi = refMidi
        self.midiMin = midiMin
        self.midiMax = midiMax

        self.numSteps = self._getTotalNumSteps()
        self.pitchGridMidi = self._getPitchGridMidi()
        self.pitchGridHz = {self._midiToHz(m) for m in self.pitchGridMidi}

    def _getTotalNumSteps(self):
        return math.ceil((self.midiMax - self.midiMin) / self.smallestMicrotone)
    
    def _getPitchGridMidi(self):
        return {step * self.smallestMicrotone + self.midiMin for step in range(self.numSteps)}

    def _hzToMidi(self, hz):
        if hz <= 0:
            print("Warning: Frequency was negative and has been converted!")
            hz = abs(hz)
        return self.refMidi + 12 * math.log2(hz / self.refFreq)
    
    def _midiToHz(self, midi):
        return self.refFreq * (2 ** ((midi - self.refMidi) / 12))
    
    def quantizeHz(self, hz):
        quantizedHz = min(self.pitchGridHz, key=lambda x: abs(x - hz))
        return quantizedHz