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
# Dynamic markings
# ---------------------------------------------------------------------------
from .Dynamics import (
    DYNAMIC_MARKINGS,
    dynamicMarkingToVelocity,
    parseDynamicMarking,
)

# ---------------------------------------------------------------------------
# Algorithmic tools
# ---------------------------------------------------------------------------
from .CellularAutomata  import CellularAutomaton, CellularRules
from .LSystem           import LSystem, ProductionRule, ProductionRules, Turtle, TurtleResult, TurtleSegment
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
# Top-level composition object
# ---------------------------------------------------------------------------
from .GreasyPidgin import GreasyPidgin
