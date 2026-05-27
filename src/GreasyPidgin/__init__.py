"""
GreasyPidgin
============
A Python library for algorithmic composition.

https://www.16161d.net
sem@16161d.net
"""

__version__ = "0.9.2"
__author__  = "Sem Ribeiro Albuquerque Wendt"

print(
    f"\n"
    f"         ,--.          \n"
    f"        ( @° \\         \n"
    f"       <´,..·_\\        \n"
    f"         )_.-'/`·,     \n"
    f"        /-'``     `·,  \n"
    f"       |  GREASY   0)`·-___             \n"
    f"        \\ PIDGIN  0) 0)0 );)`--,__      \n"
    f"         \\,    _:0) 0)0_);;):;)-->>     \n"
    f"           \"-,   ,--´                   \n"
    f"              \\,/                       \n"
    f"            ,_//                        \n"
    f"           ,_-'-,                       \n"
    f"\n"
    f"   GreasyPidgin v{__version__}\n"
)

# ---------------------------------------------------------------------------
# Core domain objects
# ---------------------------------------------------------------------------
from .TemporalObject    import TemporalObject
from .Phonon            import Phonon
from .Gesture           import Gesture
from .Phrase            import Phrase

# ---------------------------------------------------------------------------
# Grids
# ---------------------------------------------------------------------------
from .Grid              import Grid
from .TimeGrid          import TimeGrid, RQQ, beatToSec, secToBeat
from .PitchGrid         import PitchGrid

# ---------------------------------------------------------------------------
# Tuning systems and scale masks
# ---------------------------------------------------------------------------
from .TuningSystemAndScaleMask import (
    TuningSystem,
    ScaleMask,
    TUNING_SYSTEMS,
)

# ---------------------------------------------------------------------------
# Pitch utilities
# ---------------------------------------------------------------------------
from .Pitch import (
    spntom,
    mtof,
    ftom,
    spntof,
    forceIntoRangeMidi,
)

# ---------------------------------------------------------------------------
# Algorithmic tools
# ---------------------------------------------------------------------------
from .CellularAutomata  import CellularAutomaton, CellularRules
from .LSystem           import LSystem, ProductionRule, ProductionRules
from .MarkovChains      import MarkovChain, MarkovRule, MarkovRules

# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------
from .Exporters         import MidiExporter, JsonExporter, CsvExporter

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
from .Normalisation     import scale
from .IterableOperations import flatten

# ---------------------------------------------------------------------------
# Top-level GreasyPidgin composition object (legacy, kept for compatibility)
# ---------------------------------------------------------------------------
from .TemporalObject import TemporalObject as _TemporalObject


def _ensureType(obj, cls):
    if not isinstance(obj, cls):
        obj = cls(obj)
    return obj


class GreasyPidgin(_TemporalObject):
    """
    Top-level composition container.

    Holds an ensemble, a TimeGrid, a PitchGrid, and a collection of
    TemporalObjects (Gestures, Phrases, etc.).
    """

    def __init__(
        self,
        name:             str   = "GreasyPidgin",
        *,
        timeGrid:         TimeGrid  | None = None,
        pitchGrid:        PitchGrid | None = None,
        temporalObjects:  list            = None,
        startTimeSec:     float           = 0.0,
        durationSec:      float           = 0.0,
        bpm:              float           = 60.0,
    ) -> None:
        self.name          = name
        self.timeGrid      = timeGrid  if timeGrid  is not None else TimeGrid([])
        self.pitchGrid     = pitchGrid if pitchGrid is not None else PitchGrid([])
        super().__init__(
            startTimeSec,
            durationSec,
            bpm      = bpm,
            children = temporalObjects or [],
        )

    def __repr__(self) -> str:
        return (
            f"GreasyPidgin(\n"
            f"  name       : {self.name}\n"
            f"  version    : {__version__}\n"
            f"  start      : {self.startTimeSec:.3f}s\n"
            f"  duration   : {self.durationSec:.3f}s\n"
            f"  bpm        : {self.bpm}\n"
            f"  children   : {len(self.children)}\n"
            f")"
        )