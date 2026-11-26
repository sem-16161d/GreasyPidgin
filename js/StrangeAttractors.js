/*
StrangeAttractors.js — JavaScript port of GreasyPidgin/StrangeAttractors.py
(formulas from https://www.dynamicmath.xyz/strange-attractors/)

Each attractor maps a position [x, y, z] to a velocity [dx, dy, dz];
buildTrajectory integrates it with RK4.

    Max:   var SA = require("StrangeAttractors");   SA.buildTrajectory(SA.lorenz, [0.1, 0, 0], 0.01, 1000)
    Node:  const { buildTrajectory, lorenz } = require("./StrangeAttractors");
*/

const add = (a, b, s = 1) => a.map((v, i) => v + s * b[i]);

/** One RK4 step: position + dt * weighted mean of four velocity samples. */
function rk4Step(equations, position, dt) {
    const k1 = equations(position);
    const k2 = equations(add(position, k1, 0.5 * dt));
    const k3 = equations(add(position, k2, 0.5 * dt));
    const k4 = equations(add(position, k3, dt));
    return position.map((p, i) => p + dt / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]));
}

/** `steps` visited positions starting at `start`. */
function buildTrajectory(equations, start, dt = 0.01, steps = 80000) {
    const out = [];
    let pos = start.map(Number);
    for (let i = 0; i < steps; i++) {
        out.push(pos);
        pos = rk4Step(equations, pos, dt);
    }
    return out;
}

const lorenz = ([x, y, z]) => { const [s, r, b] = [10, 28, 8 / 3]; return [s * (y - x), x * (r - z) - y, x * y - b * z]; };
const rossler = ([x, y, z]) => { const [a, b, c] = [0.2, 0.2, 5.7]; return [-(y + z), x + a * y, b + z * (x - c)]; };
const thomas = ([x, y, z]) => { const b = 0.208186; return [Math.sin(y) - b * x, Math.sin(z) - b * y, Math.sin(x) - b * z]; };
const halvorsen = ([x, y, z]) => {
    const a = 1.89;
    return [-a * x - 4 * y - 4 * z - y ** 2, -a * y - 4 * z - 4 * x - z ** 2, -a * z - 4 * x - 4 * y - x ** 2];
};

if (typeof exports !== "undefined") Object.assign(exports, { rk4Step, buildTrajectory, lorenz, rossler, thomas, halvorsen });
