from GreasyPidgin.Grid import Grid
from GreasyPidgin.Normalisation import scale

class DynamicGrid(Grid):
    def __init__(
        self,
        dynamicStepdB: float = 3.0,
        maxdB: float = 100.0,
        possibleDynamicsString=None,
        minVelMidi=20, maxVelMidi=120
    ) -> None:

        if possibleDynamicsString is None:
            possibleDynamicsString = [
                "ppppp", "pppp", "ppp",
                "pp", "p", "mp",
                "mf", "f", "ff",
                "fff", "ffff", "fffff",
            ]

        dynamicStepdB = float(dynamicStepdB)
        maxdB = float(maxdB)

        # build grid values (descending in dB)
        values = Grid.series(
            start=maxdB, 
            step=-dynamicStepdB, 
            size=len(possibleDynamicsString))

        # init base Grid (set) with these values
        super().__init__(values)
        self.possibleDynamicsString = possibleDynamicsString
        self.dynamicStepdB = dynamicStepdB
        self.maxdB = maxdB
        self.mindB = min(values)
        self.minVelMidi=int(minVelMidi)
        self.maxVelMidi=int(maxVelMidi)

        # mapping: quiet -> low dB, loud -> high dB
        # ppppp ... fffff (as given)
        self.dynamicMapping ={}
        for dB, str in zip(values.sorted(),self.possibleDynamicsString):
            self.dynamicMapping[str] = {
                "velMidi": round(
                    scale(
                        dB, 
                        self.mindB, self.maxdB, 
                        self.minVelMidi, self.maxVelMidi)),
                "db": dB
            }
