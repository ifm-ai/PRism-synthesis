"""
Hidden verifier tests for BigDL-LLM benchmark harness fix.

This test verifies that the BigDLLM class correctly captures and retains
the optimize_model and use_cache flags from the constructor kwargs.

Bug: The original code retrieved these flags from kwargs.get() after they
     had already been popped from kwargs in the loop above.

Fix: The code should retrieve these flags from self.bigdl_llm_kwargs.get()
     where they were stored during the kwargs iteration.

Test strategy:
- Read the source file and extract the kwargs handling logic
- Execute the FULL logic including the kwargs loop and the flag assignments
- The test will FAIL on buggy code and PASS on fixed code
"""

import pytest
import sys
import re
import os

# Add the BigDL-LLM source path for imports
# Use SOURCE_ROOT env var if set, otherwise default to /workspace
SOURCE_ROOT = os.environ.get('SOURCE_ROOT', '/workspace')
sys.path.insert(0, f'{SOURCE_ROOT}/python/llm/src')
sys.path.insert(0, f'{SOURCE_ROOT}/python/llm')


def extract_and_execute_full_kwargs_logic(kwargs_input):
    """
    Extract and execute the FULL kwargs handling logic from BigDLLM source.

    This function reads the source file, extracts the complete kwargs handling
    logic (including the loop that pops kwargs and the flag assignments),
    and executes them to test the behavior.

    Args:
        kwargs_input: Dictionary of keyword arguments

    Returns:
        Dictionary containing the final bigdl_llm_kwargs after processing
    """
    # Use SOURCE_ROOT env var if set, otherwise default to /workspace
    source_root = os.environ.get('SOURCE_ROOT', '/workspace')
    source_file = f'{source_root}/python/llm/dev/benchmark/harness/bigdl_llm.py'
    with open(source_file, 'r') as f:
        source_code = f.read()

    # Create a namespace to execute the logic
    namespace = {
        'kwargs': kwargs_input.copy(),
        'bigdl_llm_kwargs': {},
        'AutoCausalLM_ARGS': ['self', 'args', 'kwargs'],  # Simplified
    }

    # First, execute the loop that moves kwargs to bigdl_llm_kwargs
    # This is the pattern from the source:
    #   keys = list(kwargs.keys())
    #   for k in keys:
    #       if k not in self.AutoCausalLM_ARGS:
    #           self.bigdl_llm_kwargs[k] = kwargs.pop(k)

    keys = list(namespace['kwargs'].keys())
    for k in keys:
        if k not in namespace['AutoCausalLM_ARGS']:
            namespace['bigdl_llm_kwargs'][k] = namespace['kwargs'].pop(k)

    # Now find and execute the lines that assign use_cache and optimize_model
    lines = source_code.split('\n')

    for line in lines:
        stripped = line.strip()
        # Look for the assignment lines for use_cache and optimize_model
        if "self.bigdl_llm_kwargs['use_cache']" in stripped or \
           'self.bigdl_llm_kwargs["use_cache"]' in stripped:
            # Replace 'self.bigdl_llm_kwargs' with 'bigdl_llm_kwargs' for execution
            exec_line = stripped.replace("self.bigdl_llm_kwargs", "bigdl_llm_kwargs")
            exec(exec_line, namespace)
        if "self.bigdl_llm_kwargs['optimize_model']" in stripped or \
           'self.bigdl_llm_kwargs["optimize_model"]' in stripped:
            exec_line = stripped.replace("self.bigdl_llm_kwargs", "bigdl_llm_kwargs")
            exec(exec_line, namespace)

    return namespace['bigdl_llm_kwargs']


class TestBigDLLM_RuntimeBehavior:
    """
    Tests that verify the actual runtime behavior of BigDLLM kwargs handling.

    These tests read the source file and execute the FULL kwargs handling logic
    to verify that the fix correctly retains the optimize_model and use_cache flags.
    """

    def test_optimize_model_false_is_retained(self):
        """
        Test that optimize_model=False is retained in bigdl_llm_kwargs.

        This test reads the actual source and executes the kwargs handling logic.

        Expected behavior with FIXED code:
        - optimize_model=False should be retained

        Expected behavior with BUGGY code:
        - optimize_model=False is lost, defaults to True
        """
        kwargs = {'optimize_model': False, 'use_cache': True}
        result = extract_and_execute_full_kwargs_logic(kwargs)

        assert result.get('optimize_model') is False, \
            f"optimize_model=False should be retained, got {result.get('optimize_model')}"

    def test_use_cache_false_is_retained(self):
        """
        Test that use_cache=False is retained in bigdl_llm_kwargs.

        Expected behavior with FIXED code:
        - use_cache=False should be retained

        Expected behavior with BUGGY code:
        - use_cache=False is lost, defaults to True
        """
        kwargs = {'optimize_model': True, 'use_cache': False}
        result = extract_and_execute_full_kwargs_logic(kwargs)

        assert result.get('use_cache') is False, \
            f"use_cache=False should be retained, got {result.get('use_cache')}"

    def test_both_flags_false_are_retained(self):
        """
        Test that both optimize_model=False and use_cache=False are retained.

        This is the key test case that exercises the exact bug scenario.
        """
        kwargs = {'optimize_model': False, 'use_cache': False}
        result = extract_and_execute_full_kwargs_logic(kwargs)

        assert result.get('optimize_model') is False, \
            f"optimize_model=False should be retained, got {result.get('optimize_model')}"
        assert result.get('use_cache') is False, \
            f"use_cache=False should be retained, got {result.get('use_cache')}"

    def test_default_values_when_not_provided(self):
        """
        Test that default values (True) are used when flags are not provided.

        This test ensures the fix doesn't break the default behavior.
        """
        kwargs = {'other_arg': 'value'}
        result = extract_and_execute_full_kwargs_logic(kwargs)

        assert result.get('optimize_model') is True, \
            f"optimize_model should default to True, got {result.get('optimize_model')}"
        assert result.get('use_cache') is True, \
            f"use_cache should default to True, got {result.get('use_cache')}"

    def test_mixed_flag_values(self):
        """
        Test with one flag True and one flag False.
        """
        kwargs = {'optimize_model': True, 'use_cache': False}
        result = extract_and_execute_full_kwargs_logic(kwargs)

        assert result.get('optimize_model') is True
        assert result.get('use_cache') is False


class TestBigDLLM_BehavioralSimulation:
    """
    Behavioral tests that simulate the exact logic patterns.

    These tests demonstrate the difference between buggy and fixed behavior
    by simulating both code patterns.
    """

    def test_fixed_pattern_retains_flags(self):
        """
        Simulate the fixed code pattern to verify it retains flags correctly.
        """
        bigdl_llm_kwargs = {}
        AutoCausalLM_ARGS = ['self', 'args', 'kwargs']

        kwargs = {'optimize_model': False, 'use_cache': False}
        keys = list(kwargs.keys())
        for k in keys:
            if k not in AutoCausalLM_ARGS:
                bigdl_llm_kwargs[k] = kwargs.pop(k)

        # FIXED CODE pattern
        bigdl_llm_kwargs['use_cache'] = bigdl_llm_kwargs.get('use_cache', True)
        bigdl_llm_kwargs['optimize_model'] = bigdl_llm_kwargs.get('optimize_model', True)

        assert bigdl_llm_kwargs.get('optimize_model') is False
        assert bigdl_llm_kwargs.get('use_cache') is False

    def test_buggy_pattern_loses_flags(self):
        """
        Simulate the buggy code pattern to verify it loses flags.

        This demonstrates the bug that the fix addresses.
        """
        bigdl_llm_kwargs = {}
        AutoCausalLM_ARGS = ['self', 'args', 'kwargs']

        kwargs = {'optimize_model': False, 'use_cache': False}
        keys = list(kwargs.keys())
        for k in keys:
            if k not in AutoCausalLM_ARGS:
                bigdl_llm_kwargs[k] = kwargs.pop(k)

        # BUGGY CODE pattern
        bigdl_llm_kwargs['use_cache'] = kwargs.get('use_cache', True)
        bigdl_llm_kwargs['optimize_model'] = kwargs.get('optimize_model', True)

        # The buggy code loses the False values
        assert bigdl_llm_kwargs.get('optimize_model') is True
        assert bigdl_llm_kwargs.get('use_cache') is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
