# GreasyPidgin/Ensemble.py
from GreasyPidgin.DynamicGrid import DynamicGrid
from GreasyPidgin.PitchGrid import PitchGrid
from GreasyPidgin.TimeGrid import TimeGrid
from GreasyPidgin.Instruments import STANDARD_INSTRUMENTS
from GreasyPidgin.Player import Player


class Ensemble(dict):
    def __init__(
        self,
        players=[],
        *,
        instrument_palette=STANDARD_INSTRUMENTS,
    ):
        self.instrument_palette = instrument_palette
        self.players = self._formatPlayers(players, self.instrument_palette)
        

    def _formatPlayers(self, players = [], palette = dict()):
        plist = []
        names = []
        if not isinstance(players, (list, tuple)):
            players = [players]
        for p in players:
            if isinstance(p, Player):
                plist.append(p)
            elif isinstance(p, str):
                if p in palette:
                    plist.append(Player(p))
                else:
                    plist.append(Player(name=p))
            else:
                raise ValueError(f"Ensemble._formatPlayers: can't make a Player from {p}!")
        for p in plist:
            names.append(p.name)
            self[p.name] = p
        return names

   
    def getPlayer(self, name: str):
        name = str(name)
        for p in self.players:
            if p.name == name:
                return p
        return None

    # -------------------------------------------------
    # debug
    # -------------------------------------------------
    def __repr__(self):
        
        return (
            f"Ensemble(players={len(self.players)}, names={self.players}) "
        )