"""
MarkovChains.py

A Markov chain implementation supporting arbitrary order.

Classes
-------
MarkovRule
    One transition rule: from a state (tuple of symbols) to a weighted
    distribution of next symbols.

MarkovRules
    A validated collection of MarkovRule objects. Checks that the chain
    is continuous (every reachable state has a rule).

MarkovChain
    Generates sequences by following MarkovRule transitions.
    Rules can be set manually or learned from an existing sequence.

Usage
-----
    # Manual rules (order 1)
    rules = MarkovRules([
        MarkovRule(0, [0, 1], [0.3, 0.7]),
        MarkovRule(1, [0, 1], [0.6, 0.4]),
    ])
    chain = MarkovChain(rules=rules)
    seq   = chain.getNElements(seed=0, n=20)

    # Learn from a sequence (order 2)
    chain = MarkovChain()
    chain.generateRulesFromList([0,1,0,2,1,0,1,2,0,1], order=2)
    seq = chain.getNElements(seed=(0,1), n=10)
"""

from random import choices


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _toTuple(elem) -> tuple:
    """Ensure elem is a tuple (wraps scalars and converts lists)."""
    if isinstance(elem, list):
        return tuple(elem)
    if isinstance(elem, tuple):
        return elem
    return (elem,)


def _normaliseWeights(weights: list) -> list:
    """Normalise weights to sum to 1.0."""
    total = sum(weights)
    if total <= 0:
        raise ValueError("Weights must sum to a positive number")
    return [w / total for w in weights]


# ---------------------------------------------------------------------------
# MarkovRule
# ---------------------------------------------------------------------------

class MarkovRule:
    """
    One transition rule in a Markov chain.

    Parameters
    ----------
    element : any | tuple | list
        The current state. Scalars are wrapped in a tuple.
        Tuples/lists define higher-order states.
    nextElements : list
        Possible next symbols.
    weights : list[float]
        Probability weights for each next symbol.
        Automatically normalised to sum to 1.

    Attributes
    ----------
    element : tuple
        The state as a tuple.
    order : int
        Length of the state tuple.
    nextElements : list
    weights : list[float]
        Normalised probabilities.
    """

    def __init__(self, element, nextElements: list, weights: list) -> None:
        self.element      = _toTuple(element)
        self.order        = len(self.element)
        self.nextElements = list(nextElements)

        if len(nextElements) != len(weights):
            raise ValueError(
                f"MarkovRule: nextElements ({len(nextElements)}) and "
                f"weights ({len(weights)}) must have the same length"
            )
        if len(nextElements) == 0:
            raise ValueError("MarkovRule: nextElements cannot be empty")

        self.weights = _normaliseWeights(list(weights))

    def sample(self):
        """Sample one next symbol according to the weight distribution."""
        return choices(self.nextElements, self.weights)[0]

    def __repr__(self) -> str:
        pairs = list(zip(self.nextElements, [round(w, 4) for w in self.weights]))
        return (
            f"MarkovRule({self.element!r} → "
            + " | ".join(f"{ne!r}:{w}" for ne, w in pairs)
            + ")"
        )


# ---------------------------------------------------------------------------
# MarkovRules
# ---------------------------------------------------------------------------

class MarkovRules:
    """
    A validated collection of MarkovRule objects.

    All rules must have the same order. Continuity is checked:
    every state reachable via a transition must itself have a rule.

    Attributes
    ----------
    rules : dict[tuple, MarkovRule]
    order : int | None
    elements : list[tuple]
        All states with explicit rules.
    flatElements : set
        All individual symbols appearing anywhere.
    isContinuous : bool
    missingRules : set
        States that are reachable but have no rule.
    """

    def __init__(self, rules: list | None = None) -> None:
        if rules is None:
            rules = []

        self.rules:       dict[tuple, MarkovRule] = {}
        self.order:       int | None              = None
        self.elements:    list[tuple]             = []
        self.flatElements: set                    = set()
        self.missingRules: set                    = set()
        self.isContinuous: bool                   = True

        for mr in rules:
            if not isinstance(mr, MarkovRule):
                raise TypeError(
                    f"MarkovRules: expected MarkovRule, got {type(mr).__name__}"
                )
            if self.order is None:
                self.order = mr.order
            elif mr.order != self.order:
                raise ValueError(
                    f"MarkovRules: order mismatch — "
                    f"expected {self.order}, got {mr.order} for {mr.element!r}"
                )
            if mr.element in self.rules:
                raise ValueError(
                    f"MarkovRules: duplicate rule for {mr.element!r}"
                )
            self.rules[mr.element] = mr
            self.elements.append(mr.element)
            for sym in mr.element:
                self.flatElements.add(sym)
            for sym in mr.nextElements:
                self.flatElements.add(sym)

        if self.rules:
            self.isContinuous = self._checkContinuity()

    def _checkContinuity(self) -> bool:
        """
        Check that every reachable state has a rule.
        A reachable state is any (order)-length tuple formed by taking
        the last (order-1) elements of a current state and appending
        a possible next element.
        """
        reachable = set()
        for element, rule in self.rules.items():
            for nextSym in rule.nextElements:
                nextState = tuple(list(element[1:]) + [nextSym])
                reachable.add(nextState)

        self.missingRules = reachable - set(self.elements)
        if self.missingRules:
            print(
                f"MarkovRules: chain is not continuous — "
                f"missing rules for: {self.missingRules}"
            )
            return False
        return True

    def __contains__(self, key) -> bool:
        return _toTuple(key) in self.rules

    def __getitem__(self, key) -> MarkovRule:
        return self.rules[_toTuple(key)]

    def __len__(self) -> int:
        return len(self.rules)

    def __repr__(self) -> str:
        ruleLines = "\n".join(f"  {r}" for r in self.rules.values())
        return (
            f"MarkovRules(\n"
            f"  order        : {self.order}\n"
            f"  numRules     : {len(self.rules)}\n"
            f"  elements     : {self.elements}\n"
            f"  isContinuous : {self.isContinuous}\n"
            f"  missing      : {self.missingRules or None}\n"
            f"  rules:\n{ruleLines}\n)"
        )


# ---------------------------------------------------------------------------
# MarkovChain
# ---------------------------------------------------------------------------

class MarkovChain:
    """
    Generates sequences by following Markov transitions.

    Parameters
    ----------
    rules : MarkovRules | None
    seed : any | tuple | None
        Default starting state for generation. None = must be specified
        at generation time.
    order : int
        Default order. If rules are set, inferred automatically.
    n : int
        Default number of elements to generate.

    Methods
    -------
    nextElement(element)
        Sample the next symbol given the current state.
    getNElements(*, seed, n, order)
        Generate a sequence of n symbols from seed.
    generateRulesFromList(lst, order, wrap)
        Learn transition rules from an existing sequence.
    """

    def __init__(
        self,
        *,
        rules:  MarkovRules | None = None,
        seed                       = None,
        order:  int                = 1,
        n:      int                = 0,
    ) -> None:
        self.rules  = rules if rules is not None else MarkovRules()
        self.seed   = seed
        self.order  = self.rules.order if (self.rules.order is not None) else order
        self.n      = n

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def nextElement(self, element):
        """
        Sample one next symbol from the current state.

        Parameters
        ----------
        element : any | tuple | list
            Current state. Converted to tuple internally.

        Returns
        -------
        The next symbol, or None if no rule exists for this state
        (with a warning).
        """
        key = _toTuple(element)
        if key not in self.rules:
            print(f"MarkovChain.nextElement: no rule for state {key!r}")
            return None
        return self.rules[key].sample()

    def getNElements(
        self,
        *,
        seed  = None,
        n:    int | None = None,
        order: int | None = None,
    ) -> list:
        """
        Generate a sequence of symbols.

        Parameters
        ----------
        seed : any | tuple | None
            Starting state. Falls back to self.seed if None.
        n : int | None
            Number of new symbols to generate. Falls back to self.n.
        order : int | None
            Markov order (context window size). Falls back to self.order.

        Returns
        -------
        list
            The seed symbols followed by n generated symbols.
        """
        seed  = seed  if seed  is not None else self.seed
        n     = n     if n     is not None else self.n
        order = order if order is not None else self.order

        if seed is None:
            raise ValueError("MarkovChain.getNElements: no seed provided")
        if n < 1:
            raise ValueError(f"MarkovChain.getNElements: n must be >= 1, got {n}")
        if order < 1:
            raise ValueError(f"MarkovChain.getNElements: order must be >= 1, got {order}")

        out = list(_toTuple(seed))

        for _ in range(n):
            state   = _toTuple(out[-order:])
            nextSym = self.nextElement(state)
            if nextSym is None:
                print(
                    f"MarkovChain.getNElements: chain broken at state {state!r}, "
                    f"stopping early"
                )
                break
            out.append(nextSym)

        return out

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------

    def generateRulesFromList(
        self,
        lst:   list,
        order: int  = 1,
        wrap:  bool = True,
    ) -> None:
        """
        Learn transition probabilities from an existing sequence.

        Parameters
        ----------
        lst : list
            The source sequence of symbols.
        order : int
            Markov order (context window size).
        wrap : bool
            If True, wrap the sequence (connect end back to start),
            ensuring every state has at least one outgoing transition.

        The resulting rules are stored in self.rules.
        """
        if len(lst) < order + 1:
            raise ValueError(
                f"MarkovChain.generateRulesFromList: sequence too short "
                f"(length {len(lst)}) for order {order} — need at least {order+1}"
            )

        seq = list(lst)
        if wrap:
            seq = seq + seq[:order]

        # collect (state, nextSymbol) pairs
        pairs: list[tuple[tuple, any]] = []
        for i in range(len(seq) - order):
            state   = _toTuple(seq[i:i + order])
            nextSym = seq[i + order]
            pairs.append((state, nextSym))

        # group by state
        stateMap: dict[tuple, list] = {}
        for state, nextSym in pairs:
            if state not in stateMap:
                stateMap[state] = []
            stateMap[state].append(nextSym)

        # build MarkovRule objects
        newRules: list[MarkovRule] = []
        for state, nextSymbols in stateMap.items():
            uniqueNext   = list(dict.fromkeys(nextSymbols))  # preserve order, deduplicate
            weightCounts = [nextSymbols.count(s) for s in uniqueNext]
            newRules.append(MarkovRule(state, uniqueNext, weightCounts))

        self.rules = MarkovRules(newRules)
        self.order = order

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"MarkovChain(\n"
            f"  seed   : {self.seed!r}\n"
            f"  order  : {self.order}\n"
            f"  n      : {self.n}\n"
            f"  rules  : {self.rules}\n"
            f")"
        )
