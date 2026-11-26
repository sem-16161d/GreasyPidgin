import numpy as np

# claude sketch, TODO: Implement properly as class!
# formulas from https://www.dynamicmath.xyz/strange-attractors/

# ─────────────────────────────────────────────
# THE ENGINE: RK4 integrator
# Given: current position, the equations, and dt
# Returns: next position
# ─────────────────────────────────────────────
def rk4_step(equations, position, dt):
    # Sample velocity 4 times, blending start/mid/end of the step
    k1 = equations(position)
    k2 = equations(position + 0.5 * dt * k1)
    k3 = equations(position + 0.5 * dt * k2)
    k4 = equations(position + dt * k3)
    # Weighted average of the 4 samples
    return position + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)

def build_trajectory(equations, start, dt=0.01, steps=80_000):
    """Run the simulation and collect all visited points."""
    trajectory = np.empty((steps, 3))
    pos = np.array(start, dtype=float)
    for i in range(steps):
        trajectory[i] = pos
        pos = rk4_step(equations, pos, dt)
    return trajectory

# ─────────────────────────────────────────────
# THE ATTRACTORS: each is just 3 equations
# Input:  [x, y, z]  ← current position
# Output: [dx, dy, dz]  ← velocity in each direction
# ─────────────────────────────────────────────

def lorenz(p):
    x, y, z = p
    sigma, rho, beta = 10, 28, 8/3
    dx = sigma * (y - x)
    dy = x * (rho - z) - y
    dz = x * y - beta * z
    return np.array([dx, dy, dz])

def rossler(p):
    x, y, z = p
    a, b, c = 0.2, 0.2, 5.7
    dx = -(y + z)
    dy = x + a * y
    dz = b + z * (x - c)
    return np.array([dx, dy, dz])

def thomas(p):
    x, y, z = p
    b = 0.208186
    dx = np.sin(y) - b * x
    dy = np.sin(z) - b * y
    dz = np.sin(x) - b * z
    return np.array([dx, dy, dz])

def halvorsen(p):
    x, y, z = p
    a = 1.89
    dx = -a*x - 4*y - 4*z - y**2
    dy = -a*y - 4*z - 4*x - z**2
    dz = -a*z - 4*x - 4*y - x**2
    return np.array([dx, dy, dz])
