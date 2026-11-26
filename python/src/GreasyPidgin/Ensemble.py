# GreasyPidgin/Ensemble.py
from GreasyPidgin.Instruments import STANDARD_INSTRUMENTS
from GreasyPidgin.Player import Player


class Ensemble(dict):
    """
    A dict of Players by name. Players can be given as Player objects or
    as instrument names from the palette ('flute') or plain names. A name
    used twice gets a number: 'flute', 'flute_2', ...
    self.players keeps the names in order.
    """

    def __init__(
        self,
        players=None,
        *,
        instrument_palette=STANDARD_INSTRUMENTS,
    ):
        super().__init__()
        self.instrument_palette = instrument_palette
        self.players = self._formatPlayers(players or [], self.instrument_palette)

    def _formatPlayers(self, players, palette):
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
            name, k = p.name, 2
            while name in self:
                name, k = f"{p.name}_{k}", k + 1
            p.name = name
            names.append(name)
            self[name] = p
        return names

   
    def getPlayer(self, name: str):
        return self.get(str(name))

    # -------------------------------------------------
    # debug
    # -------------------------------------------------
    def __repr__(self):
        
        return (
            f"Ensemble(players={len(self.players)}, names={self.players}) "
        )