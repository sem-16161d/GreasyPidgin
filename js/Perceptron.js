/*
Perceptron.js — JavaScript port of GreasyPidgin/Perceptron.py
(derived from Joshua Ebner's https://sharpsight.ai/blog/python-perceptron-from-scratch/)

A single neuron: weights + bias, trained example by example.
activationFunction: 'identity' (linear regression), 'binary', 'tanh', 'ReLu'.

    Max:   var Perceptron = require("Perceptron").Perceptron;
    Node:  const { Perceptron } = require("./Perceptron");

    const p = new Perceptron({ learning_rate: 0.05, n_iterations: 2000 });
    p.fit([[1], [2]], [2, 4]);
    p.predict([3]);   // ~6
*/

const ACTIVATIONS = {
    identity: x => x,
    binary: x => (x > 0 ? 1 : 0),
    tanh: Math.tanh,
    ReLu: x => (x > 0 ? x : 0),
};

class Perceptron {
    constructor({ learning_rate = 0.01, n_iterations = 1000, activationFunction = "identity", verbose = false } = {}) {
        if (!Object.hasOwn(ACTIVATIONS, activationFunction)) {
            throw new Error(`Perceptron: unknown activationFunction '${activationFunction}', use one of ${Object.keys(ACTIVATIONS).join(", ")}`);
        }
        Object.assign(this, { learning_rate, n_iterations, activationFunction, verbose, weights: null, bias: null, n: 0 });
    }

    activation_function(netInput) { return ACTIVATIONS[this.activationFunction](netInput); }

    _net(features) { return features.reduce((acc, f, i) => acc + f * this.weights[i], this.bias); }

    /** features: array of examples (arrays of numbers); targets: one number per example. */
    fit(features, targets) {
        const nFeatures = features[0].length;
        this.weights = Array.from({ length: nFeatures }, () => Math.random() - 0.5);
        this.bias = Math.random() - 0.5;
        this.n = 0;
        for (let it = 0; it < this.n_iterations; it++) {
            features.forEach((ex, i) => {
                const error = targets[i] - this.activation_function(this._net(ex));
                if (this.verbose && this.n % 10000 === 0) {
                    const msg = `absolute error: ${Math.abs(error)}`;
                    if (typeof post === "function") post(msg + "\n"); else console.log(msg);
                }
                const correction = this.learning_rate * error;
                this.weights = this.weights.map((w, j) => w + correction * ex[j]);
                this.bias += correction;
                this.n++;
            });
        }
    }

    /** One example (array) -> number, or several (array of arrays) -> array. */
    predict(features) {
        return Array.isArray(features[0]) ? features.map(f => this.activation_function(this._net(f))) : this.activation_function(this._net(features));
    }
}

if (typeof exports !== "undefined") exports.Perceptron = Perceptron;
