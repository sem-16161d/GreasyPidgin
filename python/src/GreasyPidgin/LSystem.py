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

Turtle
    Interprets a generation as turtle graphics (F = draw forward,
    + / - = turn, [ / ] = branch) and returns the drawn line segments,
    which can be plotted, exported as SVG or mapped to other parameters.

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

    # Koch snowflake, drawn with the turtle
    ls = LSystem.fromStrings('F++F++F', {'F': 'F-F++F-F'})
    ls.iterate(4)
    result = ls.interpret(angle=60)       # -> TurtleResult (line segments)
    Turtle.plot(result)                   # matplotlib window
    Turtle.toSvg(result, path='koch.svg')

    # branching snowflake arms (six-fold symmetry)
    ls = LSystem.fromStrings('[A]+[A]+[A]+[A]+[A]+[A]', {'A': 'F[+FA][-FA]F'})
    ls.iterate(3)
    Turtle.plot(ls.interpret(angle=60), colorByDepth=True)
"""

import math
from dataclasses import dataclass, field


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

    @classmethod
    def fromStrings(cls, rules: dict, extraSymbols: str = "") -> "ProductionRules":
        """
        Build rules from strings, one character per symbol.

            ProductionRules.fromStrings({'F': 'F-F++F-F'})

        Values may also be lists of symbols. Characters in `extraSymbols`
        that have no rule of their own (e.g. the symbols of an axiom) get
        identity rules, so they are known to the system.
        """
        ruleList = [
            ProductionRule(pred, list(succ) if isinstance(succ, str) else succ)
            for pred, succ in rules.items()
        ]
        known = set(rules)
        for c in extraSymbols:
            if c not in known and not c.isspace():
                ruleList.append(ProductionRule(c, [c]))
                known.add(c)
        return cls(ruleList)

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

    @classmethod
    def fromStrings(cls, axiom: str, rules: dict) -> "LSystem":
        """
        Build an LSystem from strings, one character per symbol (spaces are
        ignored in the axiom):

            LSystem.fromStrings('F++F++F', {'F': 'F-F++F-F'})
        """
        axiomSymbols = [c for c in axiom if not c.isspace()]
        return cls(axiomSymbols, ProductionRules.fromStrings(rules, "".join(axiomSymbols)))

    def interpret(self, turtle: "Turtle | None" = None,
                  generation: int | None = None, **turtleKwargs) -> "TurtleResult":
        """
        Draw a generation with a Turtle and return the TurtleResult.

        turtle      : a configured Turtle; or leave it out and pass Turtle
                      options directly, e.g. ls.interpret(angle=60)
        generation  : which generation to draw (default: the latest)
        """
        if turtle is None:
            turtle = Turtle(**turtleKwargs)
        elif turtleKwargs:
            raise TypeError("LSystem.interpret: pass either a Turtle or Turtle options, not both")
        gen = self.currentGeneration() if generation is None else self.generationAt(generation)
        return turtle.run(gen)

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

# ---------------------------------------------------------------------------
# Turtle graphics
# ---------------------------------------------------------------------------

@dataclass
class TurtleSegment:
    """One line drawn by the turtle.

    start, end : (x, y) coordinates
    heading    : direction in degrees (0 = right, 90 = up)
    depth      : bracket nesting level ([ ... ]) at which it was drawn
    index      : position of the drawing symbol in the generation
    length     : length of the segment
    """
    start:   tuple
    end:     tuple
    heading: float
    depth:   int
    index:   int
    length:  float


@dataclass
class TurtleResult:
    """Everything a Turtle drew.

    segments : list[TurtleSegment] in drawing order
    bounds   : (xMin, yMin, xMax, yMax) of everything visited
    maxDepth : deepest bracket nesting reached
    """
    segments: list = field(default_factory=list)
    bounds:   tuple = (0.0, 0.0, 0.0, 0.0)
    maxDepth: int = 0

    def __len__(self) -> int:
        return len(self.segments)

    def __repr__(self) -> str:
        x0, y0, x1, y1 = self.bounds
        return (
            f"TurtleResult(segments={len(self.segments)}, maxDepth={self.maxDepth}, "
            f"bounds=({x0:.3g}, {y0:.3g}, {x1:.3g}, {y1:.3g}))"
        )


class Turtle:
    """
    Turtle-graphics interpreter for L-System generations.

    The turtle starts at startPosition facing startHeading (degrees, 0 = right,
    90 = up, counter-clockwise positive) and reads the symbols one by one:

        F       draw forward one step          (draw)
        f       move forward without drawing   (move)
        +       turn left by `angle`           (left)
        -       turn right by `angle`          (right)
        |       turn around, 180 degrees       (turnAround)
        [       save position, heading, step   (push)
        ]       return to the last saved state (pop)
        >       step length *= lengthScale     (scaleUp)
        <       step length /= lengthScale     (scaleDown)

    Any other symbol (such as the A or X placeholders many rules use) is
    ignored. The symbols for each action can be changed: every action
    parameter takes a list of symbols, so Turtle(draw=['F', 'A', 'B'])
    draws for F, A and B alike.

    Parameters
    ----------
    angle         : turn angle in degrees (60 for snowflakes, 90 for dragon curves)
    stepLength    : length of one forward step
    lengthScale   : factor used by the scaleUp / scaleDown symbols
    startPosition : (x, y)
    startHeading  : degrees
    draw, move, left, right, turnAround, push, pop, scaleUp, scaleDown :
        lists of symbols triggering each action

    Example
    -------
    >>> ls = LSystem.fromStrings('F++F++F', {'F': 'F-F++F-F'})
    >>> ls.iterate(3)
    >>> result = Turtle(angle=60).run(ls.currentGeneration())
    >>> Turtle.plot(result)
    """

    def __init__(
        self,
        angle: float = 90.0,
        stepLength: float = 1.0,
        lengthScale: float = 1.0,
        startPosition: tuple = (0.0, 0.0),
        startHeading: float = 90.0,
        *,
        draw=("F",), move=("f",), left=("+",), right=("-",),
        turnAround=("|",), push=("[",), pop=("]",),
        scaleUp=(">",), scaleDown=("<",),
    ) -> None:
        if lengthScale <= 0:
            raise ValueError("Turtle: lengthScale must be > 0")
        self.angle         = float(angle)
        self.stepLength    = float(stepLength)
        self.lengthScale   = float(lengthScale)
        self.startPosition = (float(startPosition[0]), float(startPosition[1]))
        self.startHeading  = float(startHeading)

        self.actions: dict = {}
        for action, symbols in (
            ("draw", draw), ("move", move), ("left", left), ("right", right),
            ("turnAround", turnAround), ("push", push), ("pop", pop),
            ("scaleUp", scaleUp), ("scaleDown", scaleDown),
        ):
            if isinstance(symbols, str):
                symbols = [symbols]
            for sym in symbols:
                if sym in self.actions and self.actions[sym] != action:
                    raise ValueError(
                        f"Turtle: symbol {sym!r} is assigned to both "
                        f"{self.actions[sym]!r} and {action!r}"
                    )
                self.actions[sym] = action

    # ------------------------------------------------------------------
    def run(self, symbols) -> TurtleResult:
        """Interpret a sequence of symbols and return the drawn segments."""
        x, y    = self.startPosition
        heading = self.startHeading
        step    = self.stepLength
        depth   = 0
        stack: list = []

        segments: list = []
        xs, ys = [x], [y]
        maxDepth = 0

        for i, sym in enumerate(symbols):
            try:
                action = self.actions.get(sym)
            except TypeError:       # unhashable symbol -> not an action
                action = None
            if action is None:
                continue

            if action in ("draw", "move"):
                rad = math.radians(heading)
                nx, ny = x + step * math.cos(rad), y + step * math.sin(rad)
                if action == "draw":
                    segments.append(TurtleSegment((x, y), (nx, ny), heading, depth, i, step))
                x, y = nx, ny
                xs.append(x); ys.append(y)
            elif action == "left":
                heading += self.angle
            elif action == "right":
                heading -= self.angle
            elif action == "turnAround":
                heading += 180.0
            elif action == "push":
                stack.append((x, y, heading, step))
                depth += 1
                maxDepth = max(maxDepth, depth)
            elif action == "pop":
                if not stack:
                    raise ValueError(f"Turtle.run: unmatched {sym!r} at index {i}")
                x, y, heading, step = stack.pop()
                depth -= 1
            elif action == "scaleUp":
                step *= self.lengthScale
            elif action == "scaleDown":
                step /= self.lengthScale

        if stack:
            raise ValueError(f"Turtle.run: {len(stack)} unclosed branch(es) -- a pop symbol is missing")

        return TurtleResult(
            segments=segments,
            bounds=(min(xs), min(ys), max(xs), max(ys)),
            maxDepth=maxDepth,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def plot(result: TurtleResult, *, color="black", colorByDepth: bool = False,
             cmap: str = "viridis", linewidth: float = 1.0, ax=None,
             show: bool = True, title: str | None = None):
        """
        Draw a TurtleResult with matplotlib. Returns (fig, ax).

        colorByDepth : colour each line by its branch depth instead of `color`
        show         : call plt.show(); pass False to keep working with the
                       returned figure (e.g. to save it)
        """
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection

        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 6))
        else:
            fig = ax.figure

        lines = [(seg.start, seg.end) for seg in result.segments]
        if colorByDepth and result.segments:
            lc = LineCollection(lines, linewidths=linewidth, cmap=cmap)
            lc.set_array([seg.depth for seg in result.segments])
        else:
            lc = LineCollection(lines, linewidths=linewidth, colors=color)
        ax.add_collection(lc)

        x0, y0, x1, y1 = result.bounds
        padX = (x1 - x0) * 0.03 or 1.0
        padY = (y1 - y0) * 0.03 or 1.0
        ax.set_xlim(x0 - padX, x1 + padX)
        ax.set_ylim(y0 - padY, y1 + padY)
        ax.set_aspect("equal")
        ax.axis("off")
        if title:
            ax.set_title(title)
        fig.tight_layout()
        if show:
            plt.show()
        return fig, ax

    @staticmethod
    def toSvg(result: TurtleResult, *, size: int = 600, margin: int = 10,
              stroke: str = "black", strokeWidth: float = 1.0,
              background: str | None = None, path: str | None = None) -> str:
        """
        Render a TurtleResult as an SVG string (and write it to `path` if
        given). The y-axis is flipped so that "up" is up.
        """
        x0, y0, x1, y1 = result.bounds
        span = max(x1 - x0, y1 - y0, 1e-12)
        scale = (size - 2 * margin) / span
        w = (x1 - x0) * scale + 2 * margin
        h = (y1 - y0) * scale + 2 * margin

        def tx(x): return margin + (x - x0) * scale
        def ty(y): return margin + (y1 - y) * scale

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}" height="{h:.1f}" '
            f'viewBox="0 0 {w:.1f} {h:.1f}">'
        ]
        if background:
            parts.append(f'<rect width="100%" height="100%" fill="{background}"/>')
        parts.append(
            f'<g stroke="{stroke}" stroke-width="{strokeWidth}" stroke-linecap="round" fill="none">'
        )
        for seg in result.segments:
            parts.append(
                f'<line x1="{tx(seg.start[0]):.2f}" y1="{ty(seg.start[1]):.2f}" '
                f'x2="{tx(seg.end[0]):.2f}" y2="{ty(seg.end[1]):.2f}"/>'
            )
        parts.append("</g></svg>")
        svg = "\n".join(parts)
        if path is not None:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(svg)
        return svg
