'''
derived from Joshua Ebner's https://sharpsight.ai/blog/python-perceptron-from-scratch/
https://sharpsight.ai/blog/perceptrons-explained/
bias explained:
https://www.educative.io/answers/what-is-the-role-of-a-bias-in-neural-networks

'''
import numpy as np

class Perceptron():
    def __init__(self, learning_rate = 0.01, n_iterations = 1000, activationFunction = 'identity'):
        self.learning_rate = learning_rate
        self.n_iterations = n_iterations
        self.bias = None
        self.weights = None
        self.activationFunction = activationFunction
        self.n = 0
        
    
    def activation_function(self, net_input):
        output = 0.0
        match self.activationFunction:
            case "binary":
                output = np.where(net_input > 0, 1, 0)
            case "tanh":
                output = np.tanh(net_input)
            case "identity":
                output = output
            case "ReLu":
                output = np.where(net_input > 0, net_input, 0)
        return output
    
    
    def fit(self, features, targets):
        n_examples, n_features = features.shape
        
        # change these to use different initialization scheme
        self.weights = np.random.uniform(size = n_features, low = -0.5, high = 0.5)
        self.bias = np.random.uniform(low = -0.5, high = 0.5)
        self.n = 0
        for _ in range(self.n_iterations):
            for example_index, example_features in enumerate(features):
                net_input = np.dot(example_features, self.weights) + self.bias
                y_predicted = self.activation_function(net_input)
                self._update_weights(example_features, targets[example_index], y_predicted)
                self.n += 1
        
        
    def _update_weights(self, example_features, y_actual, y_predicted):
        error = y_actual - y_predicted
        if self.n%10000 == 0:
            print(f"absolute error: {abs(error)}")
        weight_correction = self.learning_rate * error
        self.weights = self.weights + weight_correction * example_features
        self.bias = self.bias + weight_correction
        
    def predict(self, features):
        net_input = np.dot(features, self.weights) + self.bias
        y_predicted = self.activation_function(net_input)
        return y_predicted 
