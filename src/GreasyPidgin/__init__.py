"""
GreasyPidgin – algorithmic composition toolkit.

This project is based on the idea of TemporalObject as the main element. 

"""

from GreasyPidgin.Pitch import spntom


# from GreasyPidgin.GreasyPidgin import GreasyPidgin

from GreasyPidgin.TemporalObject import TemporalObject
from GreasyPidgin.Phonon import Phonon
from GreasyPidgin.Gesture import Gesture

from GreasyPidgin.Ensemble import Ensemble
from GreasyPidgin.Player import Player

from GreasyPidgin.Grid import Grid
from GreasyPidgin.PitchGrid import PitchGrid
from GreasyPidgin.TimeGrid import TimeGrid
from GreasyPidgin.DynamicGrid import DynamicGrid




__all__ = [
    "Grid",
    "TimeGrid",
    "note2midi",
    "PitchGrid",
    "Phonon",
    "Gesture",
]