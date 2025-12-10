import numbers

from QuantisationGrid import Grid

# 10 even numbers
g1 = Grid.series(0, 2, 10)

# 5 points from 0.0 to 1.0
g2 = Grid.interpolation(0.0, 1.0, 5)

# 12 random integers [0, 127] for a MIDI-ish grid
g3 = Grid.rand(12, 0, 127, integer=True)

# 8 Fibonacci numbers
g4 = Grid.fib(8)

# fill with index^2
g5 = Grid.fill(10, lambda i: i**2)

print(g2)