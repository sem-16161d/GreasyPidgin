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
            ensemble = Ensemble(),
            timeGrid = TimeGrid(),
            pitchGrid = PitchGrid(),
            dynamicGrid = DynamicGrid(),
            temporalObjects = [],
            startTimeSec = 0.0,
            durationSec = 0.0, 
            bpm = 60,
            ):
        self.name = name
        self.ensemble = _ensureType(ensemble, Ensemble)
        self.timeGrid = _ensureType(timeGrid, TimeGrid)
        self.pitchGrid = _ensureType(pitchGrid, PitchGrid)
        self.dynamicGrid = _ensureType(dynamicGrid, DynamicGrid)
        super().__init__(startTimeSec, durationSec,bpm = bpm)

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
              \,/
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
