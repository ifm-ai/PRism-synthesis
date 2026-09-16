"""
Hidden verifier tests for gudhi TensorFlow layers.

These tests verify that the TensorFlow layers can be instantiated without errors.
The fix removes the deprecated `dynamic=True` argument from super().__init__() calls.

Tests will FAIL on buggy code (with dynamic=True) and PASS on fixed code (without dynamic=True).

Note: These tests focus on the pure Python TensorFlow layer files and do not require
the full gudhi C++ package to be built. They test the specific behavior fixed in the PR:
removing the deprecated `dynamic=True` argument from layer constructors.
"""

import sys
import os
import numpy as np
import tensorflow as tf
import pytest

# Import perslay module directly from file to avoid package __init__.py
# which imports cubical_layer that requires C++ modules
# Use dynamic path relative to current working directory (which is the workspace)
PERSLAY_PATH = os.path.join(os.getcwd(), 'src/python/gudhi/tensorflow/perslay.py')

# Use importlib to load the perslay module directly
import importlib.util
spec = importlib.util.spec_from_file_location("perslay", PERSLAY_PATH)
perslay_module = importlib.util.module_from_spec(spec)
sys.modules['gudhi.tensorflow.perslay'] = perslay_module
spec.loader.exec_module(perslay_module)

# Export the classes from the loaded module
GridPerslayWeight = perslay_module.GridPerslayWeight
GaussianMixturePerslayWeight = perslay_module.GaussianMixturePerslayWeight
PowerPerslayWeight = perslay_module.PowerPerslayWeight
GaussianPerslayPhi = perslay_module.GaussianPerslayPhi
TentPerslayPhi = perslay_module.TentPerslayPhi
FlatPerslayPhi = perslay_module.FlatPerslayPhi
Perslay = perslay_module.Perslay


class TestPerslayLayerInstantiation:
    """
    Test that Perslay and its component layers can be instantiated without errors.
    
    The perslay.py file is pure Python and does not require C++ modules.
    The bug: layers were calling super().__init__(dynamic=True, **kwargs)
    The fix: layers should call super().__init__(**kwargs)
    
    In TensorFlow 2.21+, the `dynamic` argument is deprecated and causes
    an error when instantiating layers.
    """

    def test_grid_perslay_weight_instantiation(self):
        """Test that GridPerslayWeight can be instantiated without errors."""
        # This should not raise an error on fixed code
        # On buggy code with TensorFlow 2.21+, this raises:
        # TypeError: Layer.__init__() got an unexpected keyword argument 'dynamic'
        grid = np.random.uniform(size=[10, 10]).astype(np.float32)
        grid_bnds = np.array([[-1, 1], [-1, 1]], dtype=np.float32)
        layer = GridPerslayWeight(grid=grid, grid_bnds=grid_bnds)
        assert layer is not None
        assert layer.grid is not None

    def test_gaussian_mixture_perslay_weight_instantiation(self):
        """Test that GaussianMixturePerslayWeight can be instantiated without errors."""
        gaussians = np.array([[0.5], [0.5], [1.0], [1.0]], dtype=np.float32)
        layer = GaussianMixturePerslayWeight(gaussians=gaussians)
        assert layer is not None
        assert layer.W is not None

    def test_power_perslay_weight_instantiation(self):
        """Test that PowerPerslayWeight can be instantiated without errors."""
        layer = PowerPerslayWeight(constant=1.0, power=0.5)
        assert layer is not None
        assert layer.constant is not None

    def test_gaussian_perslay_phi_instantiation(self):
        """Test that GaussianPerslayPhi can be instantiated without errors."""
        layer = GaussianPerslayPhi(
            image_size=np.array([5, 5]),
            image_bnds=np.array([[-1, 1], [-1, 1]]),
            variance=np.float32(0.1)
        )
        assert layer is not None
        assert layer.image_size is not None

    def test_tent_perslay_phi_instantiation(self):
        """Test that TentPerslayPhi can be instantiated without errors."""
        samples = np.arange(-1.0, 1.0, 0.1, dtype=np.float32)
        layer = TentPerslayPhi(samples=samples)
        assert layer is not None
        assert layer.samples is not None

    def test_flat_perslay_phi_instantiation(self):
        """Test that FlatPerslayPhi can be instantiated without errors."""
        samples = np.arange(-1.0, 1.0, 0.1, dtype=np.float32)
        layer = FlatPerslayPhi(samples=samples, theta=np.float32(100.0))
        assert layer is not None
        assert layer.samples is not None

    def test_perslay_instantiation(self):
        """Test that Perslay can be instantiated without errors."""
        # Create Perslay components
        phi = GaussianPerslayPhi(
            image_size=np.array([5, 5]),
            image_bnds=np.array([[-1, 1], [-1, 1]]),
            variance=np.float32(0.1)
        )
        weight = PowerPerslayWeight(constant=1.0, power=0.0)

        # This should not raise an error on fixed code
        layer = Perslay(
            weight=weight,
            phi=phi,
            perm_op=tf.math.reduce_sum,
            rho=tf.identity
        )
        assert layer is not None
        assert layer.weight is not None
        assert layer.phi is not None


class TestTensorFlowLayerDynamicArgument:
    """
    Test that verifies the specific fix: removing dynamic=True from super().__init__().
    
    This test directly checks that TensorFlow layers can be instantiated with
    the current code, which should work without the deprecated dynamic argument.
    """

    def test_layer_instantiation_no_dynamic_error(self):
        """
        Test that instantiating a TensorFlow layer does not raise a dynamic argument error.
        
        This is the core test for the fix. On buggy code, instantiating any of the
        TensorFlow layers would raise:
          ValueError: Unrecognized keyword arguments passed to Layer: {'dynamic': True}
        
        On fixed code, the layers instantiate successfully.
        """
        # Try to instantiate all perslay layers
        # If any of them has dynamic=True, this will fail
        layers_to_test = [
            lambda: GridPerslayWeight(
                grid=np.random.uniform(size=[5, 5]).astype(np.float32),
                grid_bnds=np.array([[-1, 1], [-1, 1]], dtype=np.float32)
            ),
            lambda: GaussianMixturePerslayWeight(
                gaussians=np.array([[0.5], [0.5], [1.0], [1.0]], dtype=np.float32)
            ),
            lambda: PowerPerslayWeight(constant=1.0, power=0.5),
            lambda: GaussianPerslayPhi(
                image_size=np.array([5, 5]),
                image_bnds=np.array([[-1, 1], [-1, 1]]),
                variance=np.float32(0.1)
            ),
            lambda: TentPerslayPhi(samples=np.arange(-1.0, 1.0, 0.1, dtype=np.float32)),
            lambda: FlatPerslayPhi(
                samples=np.arange(-1.0, 1.0, 0.1, dtype=np.float32),
                theta=np.float32(100.0)
            ),
            lambda: Perslay(
                weight=PowerPerslayWeight(1.0, 0.0),
                phi=GaussianPerslayPhi(np.array([5, 5]), np.array([[-1, 1], [-1, 1]]), np.float32(0.1)),
                perm_op=tf.math.reduce_sum,
                rho=tf.identity
            ),
        ]

        for i, layer_factory in enumerate(layers_to_test):
            # This should not raise any error on fixed code
            layer = layer_factory()
            assert layer is not None, f"Layer {i} failed to instantiate"


class TestPerslayLayerBehavior:
    """
    Test that Perslay layers produce correct output when called.
    
    These tests verify that layers not only instantiate correctly but also
    produce expected output shapes when called with appropriate inputs.
    
    Note: Some behavior tests may fail due to pre-existing dtype issues in perslay.py
    that are unrelated to the dynamic=True fix. The instantiation tests above are
    the primary verification for the fix.
    """

    def test_power_perslay_weight_call(self):
        """Test that PowerPerslayWeight produces correct output when called."""
        weight = PowerPerslayWeight(constant=1.0, power=0.0)

        # Create a simple persistence diagram as a ragged tensor
        # Shape: [batch=1, num_points=2, dims=2]
        diagrams_data = np.array([[[0., 4.], [1., 2.]]], dtype=np.float32)
        diagrams = tf.RaggedTensor.from_tensor(tf.constant(diagrams_data, dtype=tf.float32))

        # Call the layer
        result = weight(diagrams)
        assert result is not None
        # Output should have same ragged structure as input
        assert result.shape[0] == 1  # batch size
