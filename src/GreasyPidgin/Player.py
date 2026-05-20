# Player.py
from GreasyPidgin import DynamicGrid, PitchGrid, TimeGrid
from .Instrument import Instrument
from .Instruments import STANDARD_INSTRUMENTS
from .TemporalObject import TemporalObject

class Player:
    def __init__(
        self,
        instruments = [],
        name: str = "",
        *,
        instrumentPalette = STANDARD_INSTRUMENTS,
    ) -> None:
        self.instrumentPalette = instrumentPalette
        self.instruments = []
        if isinstance(instruments, str):
            instruments = [instruments]
        for instrument in instruments:
            if instrument in instrumentPalette:
                self.instruments.append(instrumentPalette[instrument])
            else:
                raise ValueError(f"Player.init: Instrument '{instrument}' doesn't exist in given palette")
        self.name: str = str(name)
        if self.name == "":
            self.name = '_'.join([i.name for i in self.instruments])
        self.temporalObjects = TemporalObject()

    def __repr__(self) -> str:

        return (
            f"Player:\n"
            f"   name        : {self.name}\n"
            f"   instruments : {[i.name for i in self.instruments]}\n"
        )