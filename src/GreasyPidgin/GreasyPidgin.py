from GreasyPidgin.PitchGrid import PitchGrid
from GreasyPidgin.TemporalObject import TemporalObject
from GreasyPidgin.TimeGrid import TimeGrid
from GreasyPidgin.DynamicGrid import DynamicGrid
from GreasyPidgin.Ensemble import Ensemble

def _ensureType(input, cls ):
    if not isinstance(input, cls):
        input = cls(input)
    return input

class GreasyPidgin(TemporalObject):
    def __init__(
            self,
            name = "GreasyPidgin",
            *,
            ensemble = None,
            timeGrid = None,
            pitchGrid = None,
            dynamicGrid = None,
            temporalObjects = None,
            startTimeSec = 0.0,
            durationSec = 0.0,
            ):
        self.name = name
        self.ensemble = _ensureType(Ensemble() if ensemble is None else ensemble, Ensemble)
        self.timeGrid = _ensureType(TimeGrid() if timeGrid is None else timeGrid, TimeGrid)
        self.pitchGrid = _ensureType(PitchGrid() if pitchGrid is None else pitchGrid, PitchGrid)
        self.dynamicGrid = _ensureType(DynamicGrid() if dynamicGrid is None else dynamicGrid, DynamicGrid)
        super().__init__(startTimeSec, durationSec, temporalObjects)

    def __repr__(self):
        return (
            """
########################################################################

         ,--.
        ( @° \\
       <´,..·_\\
         )_.-'/`·,
        /-'``     `·,
       |  GREASY   0)`·-___
        \\ PIDGIN  0) 0)0 );)`--,__
         \\,    _:0) 0)0_);;):;)-->>
           "-,   ,--´
              \\,/
            ,_//
           ,_-'-,


            """
            f"\n   name     : {self.name}\n"
            f"   id       : {self.id}\n"
            f"   start    : {self.startTimeSec:.3f}\n"
            f"   dur      : {self.durationSec:.3f}\n"
            f"   ensemble : {self.ensemble}\n"
            f"   tmpObjs  : {len(self.children)}\n"
            )
