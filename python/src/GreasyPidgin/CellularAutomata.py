"""
CellularAutomata.py

Classes
-------
CellularRules
    Defines the rule table for a cellular automaton.
    Currently supports: Wolfram elementary (1D, 2-state, 3-cell neighbourhood).

CellularAutomaton
    Runs a cellular automaton forward in time using a CellularRules instance.
    Stores all generations and provides export to Envelope and flat list.

Usage
-----
    # Wolfram rule 30
    rule = CellularRules.elementaryWolfram(30)
    ca   = CellularAutomaton(rules=rule, dimension=1)
    ca.gen0fromInteger(1)        # single active cell
    ca.iterate(20)
    env  = ca.generationsToEnvelope()

    # Rule 110 from a random initial state
    import random
    rule = CellularRules.elementaryWolfram(110)
    ca   = CellularAutomaton(rules=rule, dimension=1, gen0=[random.randint(0,1) for _ in range(32)])
    ca.iterate(32)
    print(ca.concatenateGenerations())
"""

import numpy as np
from GreasyPidgin.Envelope import Envelope


# ---------------------------------------------------------------------------
# CellularRules
# ---------------------------------------------------------------------------

class CellularRules:
    """
    Defines the lookup table for a cellular automaton rule.

    Attributes
    ----------
    name : int | str
        Rule identifier (e.g. rule number for Wolfram rules).
    ruleType : str
        'wolfram' | 'conway'
    dimensions : int
        Spatial dimensions of the rule (1 for Wolfram, 2 for Conway).
    numStates : int
        Number of cell states (2 for binary CA).
    lookup : dict
        Maps neighbourhood strings to output state strings.
    """

    # maps ruleType → (dimensions, numStates)
    _RULE_META: dict[str, tuple[int, int]] = {
        'wolfram': (1, 2),
        'conway':  (2, 2),
    }

    def __init__(self) -> None:
        self.name       = 'nil'
        self.ruleType   = 'wolfram'
        self.dimensions = 1
        self.numStates  = 2
        self.minVal     = 0
        self.maxVal     = 1
        self.lookup:    dict[str, str] = {}

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def elementaryWolfram(cls, ruleNumber: int = 0) -> "CellularRules":
        """
        Build a Wolfram elementary CA rule (1D, 2-state, 3-cell neighbourhood).

        Rule number must be in [0, 255].
        Each of the 8 possible 3-bit neighbourhoods maps to a 0 or 1 output.

        Reference: https://atlas.wolfram.com/01/01/

        Example
        -------
        >>> rule = CellularRules.elementaryWolfram(30)
        >>> rule.lookup
        {'111': '0', '110': '0', '101': '0', '011': '1', ...}
        """
        if not 0 <= ruleNumber <= 255:
            raise ValueError(
                f"CellularRules.elementaryWolfram: ruleNumber must be 0–255, got {ruleNumber}")

        obj             = cls()
        obj.ruleType    = 'wolfram'
        obj.dimensions  = 1
        obj.numStates   = 2
        obj.name        = ruleNumber

        # 8 possible 3-bit neighbourhoods, highest first (111 → 000)
        numNeighbourhoods = 8
        ruleStr           = format(ruleNumber, f"0{numNeighbourhoods}b")
        keys              = [format(i, "03b") for i in range(numNeighbourhoods)][::-1]
        for key, bit in zip(keys, ruleStr):
            obj.lookup[key] = bit

        return obj

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def apply(self, neighbourhood: str) -> int:
        """
        Return the next state for a given neighbourhood string.

        neighbourhood : str
            Binary string of the cell and its neighbours, e.g. '010'.
        """
        match self.ruleType:
            case 'wolfram':
                return int(self.lookup[neighbourhood])
            case _:
                raise NotImplementedError(
                    f"CellularRules.apply: ruleType '{self.ruleType}' not implemented")

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"\nCellularRule:\n"
            f"  name       : {self.name}\n"
            f"  type       : {self.ruleType}\n"
            f"  dimensions : {self.dimensions}\n"
            f"  numStates  : {self.numStates}\n"
            f"  lookup     : {self.lookup}\n"
        )


# ---------------------------------------------------------------------------
# CellularAutomaton
# ---------------------------------------------------------------------------

class CellularAutomaton:
    """
    Runs a cellular automaton forward in time.

    Generations are stored in self.generations as a dict
    {generationIndex: list[int]}.

    Parameters
    ----------
    rules : CellularRules
    dimension : int
        Spatial dimension (must match rules.dimensions).
    gen0 : list[int] | None
        Initial generation. None defaults to [0].
    neighbourhoodType : str
        'moore' (default) — includes diagonals in 2D.
        'vonNeumann'      — cardinal directions only in 2D.
    """

    def __init__(
        self,
        *,
        rules: CellularRules | None = None,
        dimension: int = 1,
        gen0: list[int] | None = None,
        neighbourhoodType: str = "moore",
    ) -> None:

        self.rules             = rules if rules is not None else CellularRules()
        self.dimension         = dimension
        self.gen0              = list(gen0) if gen0 is not None else [0]
        self.neighbourhoodType = neighbourhoodType
        self.generations: dict[int, list[int]] = {0: list(self.gen0)}

        if dimension < 1:
            raise ValueError(
                f"CellularAutomaton: dimension must be >= 1, got {dimension}")

        if not self._dimensionsMatch():
            raise ValueError(
                f"CellularAutomaton: dimension mismatch — "
                f"self.dimension={self.dimension}, "
                f"rules.dimensions={self.rules.dimensions}, "
                f"gen0 shape={len(np.array(self.gen0).shape)}")

    # ------------------------------------------------------------------
    # Safety checks
    # ------------------------------------------------------------------

    def _dimensionsMatch(self) -> bool:
        gen0Dims = len(np.array(self.gen0).shape)
        return self.dimension == self.rules.dimensions == gen0Dims

    def _clipValues(self) -> None:
        """Clip gen0 values to [rules.minVal, rules.maxVal]."""
        self.gen0 = [
            int(np.clip(v, self.rules.minVal, self.rules.maxVal))
            for v in self.gen0
        ]
        self.generations[0] = list(self.gen0)

    # ------------------------------------------------------------------
    # Initial generation helpers
    # ------------------------------------------------------------------

    def gen0fromInteger(self, n: int, maxNumCells: int = -1) -> None:
        """
        Set gen0 from the binary representation of integer n.

        maxNumCells : int
            Pad to this many cells. -1 = use minimum required width.
        """
        if maxNumCells > 0:
            bits = [int(b) for b in format(n, f"0{maxNumCells}b")]
        else:
            bits = [int(b) for b in format(n, "b")]
        self.gen0 = bits
        self.generations[0] = list(bits)

    def gen0fromSingleCell(self, size: int = 32, position: int | None = None) -> None:
        """
        Set gen0 to a single active cell in a field of zeros.

        position : int | None
            Index of the active cell. None = centre.
        """
        pos  = position if position is not None else size // 2
        bits = [0] * size
        bits[pos] = 1
        self.gen0 = bits
        self.generations[0] = list(bits)

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def _lastGenerationKey(self) -> int:
        return max(self.generations.keys())

    def elementaryWolframStep(self, fromKey: int) -> None:
        """Compute one Wolfram elementary CA step from generation fromKey."""
        lastGen = self.generations[fromKey]
        genLen  = len(lastGen)
        newGen  = []
        for i in range(genLen):
            pre  = lastGen[(i - 1) % genLen]
            cur  = lastGen[i]
            post = lastGen[(i + 1) % genLen]
            key  = f"{pre}{cur}{post}"
            newGen.append(self.rules.apply(key))
        self.generations[fromKey + 1] = newGen

    def iterate(self, numIterations: int, *, startIndex: int | None = None) -> None:
        """
        Run the automaton forward for numIterations steps.

        startIndex : int | None
            Generation to start from. None = latest generation.
        """
        if startIndex is None:
            fromKey = self._lastGenerationKey()
        elif startIndex in self.generations:
            fromKey = startIndex
        else:
            raise ValueError(
                f"CellularAutomaton.iterate: {startIndex} not in generations "
                f"{list(self.generations.keys())}")

        match self.rules.ruleType:
            case 'wolfram':
                for _ in range(numIterations):
                    self.elementaryWolframStep(fromKey)
                    fromKey += 1
            case _:
                raise NotImplementedError(
                    f"CellularAutomaton.iterate: ruleType "
                    f"'{self.rules.ruleType}' not implemented")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def generationsToEnvelope(self) -> Envelope:
        """
        Convert generations to an Envelope.

        Each generation's binary cells are interpreted as a binary number.
        The envelope has one breakpoint per generation:
            x = generation index
            y = integer value of that generation's binary cells
        """
        breakpoints = []
        for genIdx in sorted(self.generations.keys()):
            gen    = self.generations[genIdx][::-1]   # LSB first
            intVal = sum(2**i * g for i, g in enumerate(gen))
            breakpoints.append((genIdx, intVal))
        return Envelope(breakpoints)

    def concatenateGenerations(self) -> list[int]:
        """Return all generations flattened into a single list."""
        result = []
        for genIdx in sorted(self.generations.keys()):
            result += self.generations[genIdx]
        return result

    def generationsAsArray(self) -> np.ndarray:
        """Return all generations as a 2D numpy array (rows = generations)."""
        keys = sorted(self.generations.keys())
        return np.array([self.generations[k] for k in keys])

    def printGenerations(self, on: str = "█", off: str = "·") -> None:
        """Pretty-print all generations as a text grid."""
        for genIdx in sorted(self.generations.keys()):
            row = "".join(on if c else off for c in self.generations[genIdx])
            print(f"{genIdx:>4} | {row}")

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        lastKey = self._lastGenerationKey()
        return (
            f"CellularAutomaton(\n"
            f"  rule       : {self.rules.name} ({self.rules.ruleType})\n"
            f"  dimension  : {self.dimension}\n"
            f"  gen0 size  : {len(self.gen0)}\n"
            f"  generations: {len(self.generations)} "
            f"(0 → {lastKey})\n"
            f")"
        )

def intToBinary(n: int, size: int = -1) -> list[int]:
        """
        Convert an integer to a list of binary digits (MSB first).
 
        Parameters
        ----------
        n : int
            The integer to convert. Must be >= 0.
        size : int
            Pad to this many digits. -1 = minimum required width.
 
        Examples
        --------
        >>> CellularAutomaton.intToBinary(6)
        [1, 1, 0]
        >>> CellularAutomaton.intToBinary(6, size=8)
        [0, 0, 0, 0, 0, 1, 1, 0]
        """
        if n < 0:
            raise ValueError(f"intToBinary: n must be >= 0, got {n}")
        if size > 0:
            return [int(b) for b in format(n, f"0{size}b")]
        return [int(b) for b in format(n, "b")] if n > 0 else [0]

def binaryToInt(bits: list[int]) -> int:
        """
        Convert a list of binary digits (MSB first) to an integer.

        The inverse of intToBinary.

        Examples
        --------
        >>> CellularAutomaton.binaryToInt([1, 1, 0])
        6
        >>> CellularAutomaton.binaryToInt([0, 0, 0, 0, 0, 1, 1, 0])
        6
        >>> CellularAutomaton.binaryToInt([0])
        0
        """
        result = 0
        for bit in bits:
            result = result * 2 + int(bit)
        return result
