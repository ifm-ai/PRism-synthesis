"""
Hidden tests to verify the LSST error model import path fix.

The fix relocates LSSTErrorModel from:
  rail.creation.degraders.lsst_error_model
to:
  rail.creation.degraders.photometric_errors

These tests verify that the example files have been updated to use the correct import path:
1. YAML configuration files use the new module path
2. Notebook files contain the correct import statements
"""

import pytest
import yaml
import json
import os


class TestYAMLConfigurations:
    """Test that YAML configuration files use the correct import path."""

    def test_pipe_example_yml(self):
        """Test pipe_example.yml uses correct module path."""
        yaml_path = "/workspace/examples/core_examples/pipe_example.yml"
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)

        # Find the LSSTErrorModel stage
        lsst_stage = None
        for stage in config.get('stages', []):
            if stage.get('classname') == 'LSSTErrorModel':
                lsst_stage = stage
                break

        assert lsst_stage is not None, "LSSTErrorModel stage not found in config"
        assert lsst_stage.get('module_name') == 'rail.creation.degraders.photometric_errors', \
            f"Expected 'rail.creation.degraders.photometric_errors', got '{lsst_stage.get('module_name')}'"

    def test_goldenspike_yml(self):
        """Test goldenspike.yml uses correct module path."""
        yaml_path = "/workspace/examples/goldenspike_examples/goldenspike.yml"
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)

        # Find all LSSTErrorModel stages
        lsst_stages = []
        for stage in config.get('stages', []):
            if stage.get('classname') == 'LSSTErrorModel':
                lsst_stages.append(stage)

        assert len(lsst_stages) > 0, "LSSTErrorModel stages not found in config"
        for stage in lsst_stages:
            assert stage.get('module_name') == 'rail.creation.degraders.photometric_errors', \
                f"Expected 'rail.creation.degraders.photometric_errors', got '{stage.get('module_name')}'"


class TestNotebookImports:
    """Test that Jupyter notebooks use the correct import statements."""

    def _check_notebook_has_correct_import(self, nb_path):
        """Check if a notebook has correct import statements for LSSTErrorModel."""
        with open(nb_path, 'r') as f:
            nb = json.load(f)

        old_path = "rail.creation.degraders.lsst_error_model"
        new_path = "rail.creation.degraders.photometric_errors"

        # Check all cells for import statements
        for cell in nb.get('cells', []):
            if cell.get('cell_type') == 'code':
                source = ''.join(cell.get('source', []))
                # Should not have old import path
                if old_path in source:
                    return False, f"Found old import path '{old_path}' in notebook"
                # If it has LSSTErrorModel import from degraders, should have new path
                if 'LSSTErrorModel' in source and 'from rail.creation.degraders' in source:
                    if new_path not in source:
                        return False, f"LSSTErrorModel not using correct path '{new_path}'"

        return True, "OK"

    def test_build_save_load_pipeline_notebook(self):
        """Test Build_Save_Load_Run_Pipeline.ipynb uses correct imports."""
        nb_path = "/workspace/examples/core_examples/Build_Save_Load_Run_Pipeline.ipynb"
        success, msg = self._check_notebook_has_correct_import(nb_path)
        assert success, msg

    def test_degradation_demo_notebook(self):
        """Test degradation-demo.ipynb uses correct imports."""
        nb_path = "/workspace/examples/creation_examples/degradation-demo.ipynb"
        success, msg = self._check_notebook_has_correct_import(nb_path)
        assert success, msg

    def test_photometric_realization_demo_notebook(self):
        """Test photometric_realization_demo.ipynb uses correct imports."""
        nb_path = "/workspace/examples/creation_examples/photometric_realization_demo.ipynb"
        success, msg = self._check_notebook_has_correct_import(nb_path)
        assert success, msg

    def test_posterior_demo_notebook(self):
        """Test posterior-demo.ipynb uses correct imports."""
        nb_path = "/workspace/examples/creation_examples/posterior-demo.ipynb"
        success, msg = self._check_notebook_has_correct_import(nb_path)
        assert success, msg

    def test_goldenspike_notebook(self):
        """Test goldenspike.ipynb uses correct imports."""
        nb_path = "/workspace/examples/goldenspike_examples/goldenspike.ipynb"
        success, msg = self._check_notebook_has_correct_import(nb_path)
        assert success, msg


class TestIntegration:
    """Integration tests that verify the fix is complete."""

    def test_yaml_load_and_parse(self):
        """Test that YAML files can be fully loaded and parsed."""
        yaml_files = [
            "/workspace/examples/core_examples/pipe_example.yml",
            "/workspace/examples/goldenspike_examples/goldenspike.yml"
        ]

        for yaml_path in yaml_files:
            with open(yaml_path, 'r') as f:
                config = yaml.safe_load(f)
            assert config is not None, f"Failed to load {yaml_path}"
            assert 'stages' in config, f"No stages found in {yaml_path}"

    def test_no_old_import_paths_in_examples(self):
        """Verify no example files contain the old import path."""
        examples_dir = "/workspace/examples"
        old_path = "rail.creation.degraders.lsst_error_model"

        files_with_old_path = []
        for root, dirs, files in os.walk(examples_dir):
            for f in files:
                if f.endswith('.yml') or f.endswith('.yaml') or f.endswith('.ipynb'):
                    file_path = os.path.join(root, f)
                    with open(file_path, 'r') as fh:
                        content = fh.read()
                        if old_path in content:
                            files_with_old_path.append(file_path)

        assert len(files_with_old_path) == 0, \
            f"Found old import path in: {', '.join(files_with_old_path)}"
