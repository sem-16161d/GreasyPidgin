from GreasyPidgin.PitchGrid import PitchGrid
from GreasyPidgin.TemporalObject import TemporalObject
from GreasyPidgin.TimeGrid import TimeGrid
from GreasyPidgin.DynamicGrid import DynamicGrid
from GreasyPidgin.Ensemble import Ensemble

def _ensureType(value, cls):
    """value as cls: instances pass, values are passed to cls(value)."""
    return value if isinstance(value, cls) else cls(value)

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
        if dynamicGrid is not None and not isinstance(dynamicGrid, DynamicGrid):
            raise TypeError("GreasyPidgin: dynamicGrid must be a DynamicGrid (e.g. DynamicGrid(dynamicStepdB=3))")
        self.dynamicGrid = dynamicGrid if dynamicGrid is not None else DynamicGrid()
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
