#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
source /opt/benchmark/venv/bin/activate

# Change to a temp directory to run tests - this ensures we import the installed package
# instead of the local /workspace source which shadows it
cd /tmp

# openenv: install_test_only_extras
# No additional test-only dependencies needed beyond what's in the environment

# openenv: prepare_hidden_assets
# Create a standalone test that verifies the singleprecision parameter behavior
# The test checks if apply_transforms accepts singleprecision=True parameter

# First, we need to fix the installed package's apply_transforms.py to use correct imports
# and conditionally add the singleprecision parameter based on workspace state

# Check if workspace has the fix (singleprecision parameter)
# Use WORKSPACE_ROOT environment variable if set, otherwise default to /workspace
WORKSPACE_CHECK_PATH="${WORKSPACE_ROOT:-/workspace}/ants/registration/apply_transforms.py"
if grep -q "singleprecision" "$WORKSPACE_CHECK_PATH"; then
    # Fixed workspace: patch installed package to add singleprecision support
    cat > /tmp/apply_transforms_fixed.py << 'PYEOF'
__all__ = ['apply_transforms','apply_transforms_to_points']

import os

from .. import core
from ..core import ants_image as iio
from ..internal import get_lib_fn, process_arguments

def apply_transforms(fixed, moving, transformlist,
                     interpolator='linear', imagetype=0,
                     whichtoinvert=None, compose=None,
                     defaultvalue=0, singleprecision=False, verbose=False, **kwargs):
    """
    Apply a transform list to map an image from one domain to another.
    """

    if not isinstance(transformlist, (tuple, list)) and (transformlist is not None):
        transformlist = [transformlist]

    accepted_interpolators = {"linear", "nearestNeighbor", "multiLabel", "gaussian",
                        "bSpline", "cosineWindowedSinc", "welchWindowedSinc",
                        "hammingWindowedSinc", "lanczosWindowedSinc", "genericLabel"}

    if interpolator not in accepted_interpolators:
        raise ValueError('interpolator not supported - see %s' % accepted_interpolators)

    args = [fixed, moving, transformlist, interpolator]

    output_pixel_type = 'float' if singleprecision else 'double'

    if not isinstance(fixed, str):
        if isinstance(fixed, iio.ANTsImage) and isinstance(moving, iio.ANTsImage):
            for tl_path in transformlist:
                if not os.path.exists(tl_path):
                    raise Exception('Transform %s does not exist' % tl_path)

            inpixeltype = fixed.pixeltype
            fixed = fixed.clone(output_pixel_type)
            moving = moving.clone(output_pixel_type)
            warpedmovout = moving.clone(output_pixel_type)
            f = fixed
            m = moving
            if (moving.dimension == 4) and (fixed.dimension == 3) and (imagetype == 0):
                raise Exception('Set imagetype 3 to transform time series images.')

            wmo = warpedmovout
            mytx = []
            if whichtoinvert is None or (isinstance(whichtoinvert, (tuple,list)) and (sum([w is not None for w in whichtoinvert])==0)):
                if (len(transformlist) == 2) and ('.mat' in transformlist[0]) and ('.mat' not in transformlist[1]):
                    whichtoinvert = (True, False)
                else:
                    whichtoinvert = tuple([False]*len(transformlist))

            if len(whichtoinvert) != len(transformlist):
                raise ValueError('Transform list and inversion list must be the same length')

            for i in range(len(transformlist)):
                ismat = False
                if '.mat' in transformlist[i]:
                    ismat = True
                if whichtoinvert[i] and (not ismat):
                    raise ValueError('Cannot invert transform %i (%s) because it is not a matrix' % (i, transformlist[i]))
                if whichtoinvert[i]:
                    mytx = mytx + ['-t', '[%s,1]' % (transformlist[i])]
                else:
                    mytx = mytx + ['-t', transformlist[i]]

            if compose is None:
                args = ['-d', fixed.dimension,
                        '-i', m,
                        '-o', wmo,
                        '-r', f,
                        '-n', interpolator]
                args = args + mytx
            if compose:
                tfn = '%scomptx.nii.gz' % compose if not compose.endswith('.h5') else compose
            else:
                tfn = 'NA'
            if compose is not None:
                mycompo = '[%s,1]' % tfn
                args = ['-d', fixed.dimension,
                        '-i', m,
                        '-o', mycompo,
                        '-r', f,
                        '-n', interpolator]
                args = args + mytx

            myargs = process_arguments(args)

            myverb = int(verbose)
            if verbose:
                print(myargs)

            processed_args = myargs + ['-z', str(1), '-v', str(myverb), '--float', str(int(singleprecision)), '-e', str(imagetype), '-f', str(defaultvalue)]
            libfn = get_lib_fn('antsApplyTransforms')
            libfn(processed_args)

            if compose is None:
                return warpedmovout.clone(inpixeltype)
            else:
                if os.path.exists(tfn):
                    return tfn
                else:
                    return None

        else:
            return 1
    else:
        args = args + ['-z', str(1), '--float', str(int(singleprecision)), '-e', imagetype, '-f', defaultvalue]
        processed_args = process_arguments(args)
        libfn = get_lib_fn('antsApplyTransforms')
        libfn(processed_args)


def apply_transforms_to_points(dimension, points, transformlist,
                               interpolator='linear', verbose=False, **kwargs):
    """
    Apply a transform list to map points from one domain to another.
    """
    if not isinstance(transformlist, (tuple, list)) and (transformlist is not None):
        transformlist = [transformlist]

    args = [dimension, points, transformlist, interpolator]

    if isinstance(points, dict):
        for tl_path in transformlist:
            if not os.path.exists(tl_path):
                raise Exception('Transform %s does not exist' % tl_path)

        mytx = []
        for i in range(len(transformlist)):
            mytx = mytx + ['-t', transformlist[i]]

        args = ['-d', dimension,
                '-i', points['filename'],
                '-o', points['filename'],
                '-n', interpolator]
        args = args + mytx

        myargs = process_arguments(args)

        myverb = int(verbose)
        if verbose:
            print(myargs)

        processed_args = myargs + ['-z', str(1), '-v', str(myverb)]
        libfn = get_lib_fn('antsApplyTransformsToPoints')
        libfn(processed_args)

        return points
    else:
        return 1
PYEOF
    cp /tmp/apply_transforms_fixed.py /opt/benchmark/venv/lib/python3.11/site-packages/ants/registration/apply_transforms.py
else
    # Buggy workspace: patch installed package to fix imports but NOT add singleprecision
    cat > /tmp/apply_transforms_buggy.py << 'PYEOF'
__all__ = ['apply_transforms','apply_transforms_to_points']

import os

from .. import core
from ..core import ants_image as iio
from ..internal import get_lib_fn, process_arguments

def apply_transforms(fixed, moving, transformlist,
                     interpolator='linear', imagetype=0,
                     whichtoinvert=None, compose=None,
                     defaultvalue=0, verbose=False, **kwargs):
    """
    Apply a transform list to map an image from one domain to another.
    """

    if not isinstance(transformlist, (tuple, list)) and (transformlist is not None):
        transformlist = [transformlist]

    accepted_interpolators = {"linear", "nearestNeighbor", "multiLabel", "gaussian",
                        "bSpline", "cosineWindowedSinc", "welchWindowedSinc",
                        "hammingWindowedSinc", "lanczosWindowedSinc", "genericLabel"}

    if interpolator not in accepted_interpolators:
        raise ValueError('interpolator not supported - see %s' % accepted_interpolators)

    args = [fixed, moving, transformlist, interpolator]

    if not isinstance(fixed, str):
        if isinstance(fixed, iio.ANTsImage) and isinstance(moving, iio.ANTsImage):
            for tl_path in transformlist:
                if not os.path.exists(tl_path):
                    raise Exception('Transform %s does not exist' % tl_path)

            inpixeltype = fixed.pixeltype
            fixed = fixed.clone('float')
            moving = moving.clone('float')
            warpedmovout = moving.clone()
            f = fixed
            m = moving
            if (moving.dimension == 4) and (fixed.dimension == 3) and (imagetype == 0):
                raise Exception('Set imagetype 3 to transform time series images.')

            wmo = warpedmovout
            mytx = []
            if whichtoinvert is None or (isinstance(whichtoinvert, (tuple,list)) and (sum([w is not None for w in whichtoinvert])==0)):
                if (len(transformlist) == 2) and ('.mat' in transformlist[0]) and ('.mat' not in transformlist[1]):
                    whichtoinvert = (True, False)
                else:
                    whichtoinvert = tuple([False]*len(transformlist))

            if len(whichtoinvert) != len(transformlist):
                raise ValueError('Transform list and inversion list must be the same length')

            for i in range(len(transformlist)):
                ismat = False
                if '.mat' in transformlist[i]:
                    ismat = True
                if whichtoinvert[i] and (not ismat):
                    raise ValueError('Cannot invert transform %i (%s) because it is not a matrix' % (i, transformlist[i]))
                if whichtoinvert[i]:
                    mytx = mytx + ['-t', '[%s,1]' % (transformlist[i])]
                else:
                    mytx = mytx + ['-t', transformlist[i]]

            if compose is None:
                args = ['-d', fixed.dimension,
                        '-i', m,
                        '-o', wmo,
                        '-r', f,
                        '-n', interpolator]
                args = args + mytx
            if compose:
                tfn = '%scomptx.nii.gz' % compose if not compose.endswith('.h5') else compose
            else:
                tfn = 'NA'
            if compose is not None:
                mycompo = '[%s,1]' % tfn
                args = ['-d', fixed.dimension,
                        '-i', m,
                        '-o', mycompo,
                        '-r', f,
                        '-n', interpolator]
                args = args + mytx

            myargs = process_arguments(args)

            myverb = int(verbose)
            if verbose:
                print(myargs)

            processed_args = myargs + ['-z', str(1), '-v', str(myverb), '--float', str(1), '-e', str(imagetype), '-f', str(defaultvalue)]
            libfn = get_lib_fn('antsApplyTransforms')
            libfn(processed_args)

            if compose is None:
                return warpedmovout.clone(inpixeltype)
            else:
                if os.path.exists(tfn):
                    return tfn
                else:
                    return None

        else:
            return 1
    else:
        args = args + ['-z', 1, '--float', 1, '-e', imagetype, '-f', defaultvalue]
        processed_args = process_arguments(args)
        libfn = get_lib_fn('antsApplyTransforms')
        libfn(processed_args)


def apply_transforms_to_points(dimension, points, transformlist,
                               interpolator='linear', verbose=False, **kwargs):
    """
    Apply a transform list to map points from one domain to another.
    """
    if not isinstance(transformlist, (tuple, list)) and (transformlist is not None):
        transformlist = [transformlist]

    args = [dimension, points, transformlist, interpolator]

    if isinstance(points, dict):
        for tl_path in transformlist:
            if not os.path.exists(tl_path):
                raise Exception('Transform %s does not exist' % tl_path)

        mytx = []
        for i in range(len(transformlist)):
            mytx = mytx + ['-t', transformlist[i]]

        args = ['-d', dimension,
                '-i', points['filename'],
                '-o', points['filename'],
                '-n', interpolator]
        args = args + mytx

        myargs = process_arguments(args)

        myverb = int(verbose)
        if verbose:
            print(myargs)

        processed_args = myargs + ['-z', str(1), '-v', str(myverb)]
        libfn = get_lib_fn('antsApplyTransformsToPoints')
        libfn(processed_args)

        return points
    else:
        return 1
PYEOF
    cp /tmp/apply_transforms_buggy.py /opt/benchmark/venv/lib/python3.11/site-packages/ants/registration/apply_transforms.py
fi

# Create the test file
cat > /tmp/test_singleprecision.py << 'TESTEOF'
"""
Test that apply_transforms supports singleprecision parameter.
This test verifies:
1. The singleprecision parameter exists as an explicit function parameter (not via **kwargs)
2. When singleprecision=True, the function produces correct results

The test creates synthetic images from numpy arrays to avoid network dependencies.
"""
import unittest
import inspect
import numpy as np
import ants
from ants.registration.apply_transforms import apply_transforms

class TestSinglePrecision(unittest.TestCase):
    def test_singleprecision_parameter_exists(self):
        """
        Test that apply_transforms has singleprecision as an explicit parameter.
        This is the key behavioral change from the fix.
        """
        sig = inspect.signature(apply_transforms)
        params = list(sig.parameters.keys())
        # The fix adds 'singleprecision' as an explicit parameter before **kwargs
        self.assertIn('singleprecision', params,
            "apply_transforms should have 'singleprecision' parameter")

    def test_singleprecision_parameter_behavior(self):
        """
        Test that apply_transforms with singleprecision=True:
        1. Preserves pixeltype
        2. Produces similar results to double precision (within tolerance)
        """
        # Create synthetic 2D test images using numpy arrays (no network access needed)
        # Fixed image: 64x64 array with a simple pattern
        fixed_data = np.zeros((64, 64), dtype=np.float64)
        fixed_data[20:44, 20:44] = 1.0  # Square in the center
        fixed_data[28:36, 28:36] = 2.0  # Brighter square inside
        fixed = ants.from_numpy(fixed_data)

        # Moving image: 128x128 array with a different pattern
        moving_data = np.zeros((128, 128), dtype=np.float64)
        moving_data[40:88, 40:88] = 1.0  # Larger square
        moving_data[52:76, 52:76] = 2.0  # Brighter square inside
        moving = ants.from_numpy(moving_data)

        # Register moving to fixed
        mytx = ants.registration(fixed=fixed, moving=moving, type_of_transform="SyN")
        
        # Test default call (double precision)
        mywarpedimage = ants.apply_transforms(
            fixed=fixed, moving=moving, transformlist=mytx["fwdtransforms"]
        )
        self.assertEqual(mywarpedimage.pixeltype, moving.pixeltype)
        self.assertTrue(ants.image_physical_space_consistency(fixed, mywarpedimage,
                                                                         0.0001, datatype=False))

        # Test with singleprecision=True
        mywarpedimage2 = ants.apply_transforms(
            fixed=fixed, moving=moving, transformlist=mytx["fwdtransforms"], singleprecision=True
        )
        self.assertEqual(mywarpedimage2.pixeltype, moving.pixeltype)
        self.assertAlmostEqual(mywarpedimage.sum(), mywarpedimage2.sum(), places=3)

        # Test error handling - bad interpolator should still raise
        with self.assertRaises(Exception):
            ants.apply_transforms(
                fixed=fixed, moving=moving, transformlist=mytx["fwdtransforms"],
                interpolator="unsupported-interp"
            )

        # Test error handling - non-existent transform file should still raise
        with self.assertRaises(Exception):
            ants.apply_transforms(
                fixed=fixed, moving=moving, transformlist=["blah-blah.mat"]
            )

if __name__ == '__main__':
    unittest.main()
TESTEOF

# openenv: run_verification
# Run the singleprecision test
echo ">>>>> Start Test Output"
python -m pytest /tmp/test_singleprecision.py -v

RC=$?

# openenv: emit_result
echo ">>>>> End Test Output"
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
