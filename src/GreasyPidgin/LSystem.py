"""
LSystem.py

Lindenmayer System (L-System) implementation.

Classes
-------
ProductionRule
    A single predecessor → successor rewriting rule.

ProductionRules
    A validated collection of ProductionRule objects.
    Constants (symbols appearing in successors but not as predecessors)
    are automatically added as identity rules (symbol → symbol).

LSystem
    Runs the L-System iteratively from an axiom using a set of
    production rules. All generations are stored.

Usage
-----
    # Algae L-System (Lindenmayer's original)
    rules = ProductionRules([
        ProductionRule('A', ['A', 'B']),
        ProductionRule('B', ['A']),
    ])
    ls = LSystem(['A'], rules)
    ls.iterate(5)
    print(ls.currentGeneration())   # ['A','B','A','A','B','A','B','A','A','B','A']

    # Koch curve (with constants F, +, -)
    rules = ProductionRules([
        ProductionRule('F', ['F', '+', 'F', '-', 'F', '-', 'F', '+', 'F']),
    ])
    ls = LSystem(['F'], rules)
    ls.iterate(3)
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten(lst) -> list:
    """Recursively flatten nested lists/tuples into a flat list."""
    result = []
    for item in lst:
        if isinstance(item, (list, tuple)):
            result.extend(_flatten(item))
        else:
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# ProductionRule
# ---------------------------------------------------------------------------

class ProductionRule:
    """
    A single rewriting rule: predecessor → successor.

    Parameters
    ----------
    predecessor : any hashable
        The symbol to be rewritten.
    successor : list
        The sequence of symbols that replaces the predecessor.
        A single non-list value is automatically wrapped in a list.

    Example
    -------
    >>> ProductionRule('A', ['A', 'B'])
    >>> ProductionRule('F', ['F', '+', 'F', '-', 'F'])
    """

    def __init__(self, predecessor, successor) -> None:
        if not isinstance(successor, (list, tuple)):
            successor = [successor]
        self.predecessor = predecessor
        self.successor   = list(successor)

    def __repr__(self) -> str:
        return f"ProductionRule({self.predecessor!r} → {self.successor!r})"


# ---------------------------------------------------------------------------
# ProductionRules
# ---------------------------------------------------------------------------

class ProductionRules:
    """
    A validated collection of ProductionRule objects.

    Duplicate predecessors are rejected. Symbols appearing in successors
    but not as predecessors are treated as constants and automatically
    given identity rules (symbol → symbol), so the lookup table is
    always complete.

    Attributes
    ----------
    rules : list[ProductionRule]
    predecessors : list
        All symbols with explicit rules.
    constants : set
        Symbols auto-added as identity rules.
    alphabet : set
        Full set of all symbols (predecessors ∪ successors).
    lookup : dict
        Maps each symbol to its successor list.
    """

    def __init__(self, productionRules: list | None = None) -> None:
        if productionRules is None:
            productionRules = []

        self.rules:        list[ProductionRule] = []
        self.predecessors: list                 = []
        self.lookup:       dict                 = {}

        # validate and register explicit rules
        for pr in productionRules:
            if not isinstance(pr, ProductionRule):
                raise TypeError(
                    f"ProductionRules: expected ProductionRule, got {type(pr).__name__}"
                )
            if pr.predecessor in self.predecessors:
                raise ValueError(
                    f"ProductionRules: duplicate predecessor {pr.predecessor!r}"
                )
            self.predecessors.append(pr.predecessor)
            self.rules.append(pr)

        # collect all symbols that appear in successors
        allSuccessorSymbols = set(
            _flatten([rule.successor for rule in self.rules])
        )

        # auto-add identity rules for constants
        self.constants = allSuccessorSymbols - set(self.predecessors)
        for c in sorted(self.constants, key=str):
            identityRule = ProductionRule(c, [c])
            self.predecessors.append(c)
            self.rules.append(identityRule)

        # build lookup
        for rule in self.rules:
            self.lookup[rule.predecessor] = rule.successor

        self.alphabet = set(self.predecessors)

    def __repr__(self) -> str:
        lines = [f"  {r}" for r in self.rules]
        return (
            f"ProductionRules(\n"
            f"  alphabet  : {self.alphabet}\n"
            f"  constants : {self.constants}\n"
            f"  rules:\n" +
            "\n".join(lines) + "\n)"
        )


# ---------------------------------------------------------------------------
# LSystem
# ---------------------------------------------------------------------------

class LSystem:
    """
    A Lindenmayer System.

    Rewrites a sequence of symbols (axiom) iteratively using production rules.
    All intermediate generations are stored in self.generations.

    Parameters
    ----------
    axiom : list
        The initial sequence of symbols. Each symbol must appear as a
        predecessor in productionRules.
    productionRules : ProductionRules

    Attributes
    ----------
    generations : dict[int, list]
        All computed generations keyed by iteration index (0 = axiom).
    """

    def __init__(self, axiom: list, productionRules: ProductionRules) -> None:
        if not isinstance(axiom, (list, tuple)):
            print(
                f"LSystem: axiom {axiom!r} is not a list, "
                f"wrapping it as [{axiom!r}]"
            )
            axiom = [axiom]

        if len(axiom) < 1:
            raise ValueError(f"LSystem: axiom is empty")

        if not isinstance(productionRules, ProductionRules):
            raise TypeError(
                f"LSystem: expected ProductionRules, got {type(productionRules).__name__}"
            )

        self.axiom           = list(axiom)
        self.productionRules = productionRules
        self.generations:    dict[int, list] = {0: list(self.axiom)}

        self._validateAxiom()

    def _validateAxiom(self) -> None:
        """Ensure every symbol in the axiom has a production rule."""
        missing = [a for a in self.axiom if a not in self.productionRules.lookup]
        if missing:
            raise ValueError(
                f"LSystem: axiom symbols {missing!r} have no production rule. "
                f"Known symbols: {list(self.productionRules.lookup.keys())}"
            )

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def _lastGenerationKey(self) -> int:
        return max(self.generations.keys())

    def step(self) -> list:
        """Compute one rewriting step from the latest generation."""
        currentGen = self.generations[self._lastGenerationKey()]
        newGen: list = []
        for symbol in currentGen:
            successor = self.productionRules.lookup.get(symbol)
            if successor is None:
                raise ValueError(
                    f"LSystem.step: no rule for symbol {symbol!r}"
                )
            newGen.extend(successor)
        nextKey = self._lastGenerationKey() + 1
        self.generations[nextKey] = newGen
        return newGen

    def iterate(self, numIterations: int, *, fromStart: bool = False) -> list:
        """
        Run the L-System for numIterations steps.

        Parameters
        ----------
        numIterations : int
        fromStart : bool
            If True, reset to the axiom before iterating.
            If False (default), continue from the latest generation.

        Returns
        -------
        The final generation as a list.
        """
        if fromStart:
            self.reset()

        for _ in range(numIterations):
            self.step()

        return self.currentGeneration()

    def reset(self) -> None:
        """Reset to generation 0 (the axiom)."""
        self.generations = {0: list(self.axiom)}

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def currentGeneration(self) -> list:
        """Return the latest computed generation."""
        return self.generations[self._lastGenerationKey()]

    def generationAt(self, index: int) -> list:
        """Return the generation at a specific iteration index."""
        if index not in self.generations:
            raise KeyError(
                f"LSystem.generationAt: generation {index} not computed yet. "
                f"Available: 0–{self._lastGenerationKey()}"
            )
        return self.generations[index]

    def lengths(self) -> dict[int, int]:
        """Return the length of each stored generation."""
        return {k: len(v) for k, v in self.generations.items()}

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        last = self._lastGenerationKey()
        cur  = self.currentGeneration()
        preview = cur[:12]
        more    = "..." if len(cur) > 12 else ""
        return (
            f"LSystem(\n"
            f"  axiom      : {self.axiom!r}\n"
            f"  generation : {last}\n"
            f"  length     : {len(cur)}\n"
            f"  current    : {preview!r}{more}\n"
            f"  rules      : {self.productionRules}\n"
            f")"
        )