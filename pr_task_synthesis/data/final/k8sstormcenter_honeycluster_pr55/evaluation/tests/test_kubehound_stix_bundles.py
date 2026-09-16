#!/usr/bin/env python3
"""
Test to validate the kubehound-stix.json bundle ID changes and new bundle additions.

The fix.patch changes:
1. Bundle IDs from "bundle--kubehound-attack-*" to "bundle--kubehound-attempt-*"
2. Adds new bundles for CE_MODULE_LOAD, CE_NET_MITM, CE_VAR_LOG_SYMLINK

This test validates these behavioral changes by checking the JSON content.
"""

import json
import sys
import os
import pytest

JSON_PATH = os.environ.get("WORKSPACE", "/workspace") + "/redis/log-notebook/kubehound-stix.json"


def load_json(filepath):
    """Load the JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def get_bundle_ids(data):
    """Extract all bundle IDs from the data."""
    return [bundle.get('id', '') for bundle in data if isinstance(bundle, dict)]


def get_bundle_names(data):
    """Extract all bundle names from the data."""
    return [bundle.get('name', '') for bundle in data if isinstance(bundle, dict)]


@pytest.fixture(scope="module")
def data():
    """Load the JSON data for all tests."""
    return load_json(JSON_PATH)


def test_no_kubehound_attack_bundles(data):
    """Test that there are NO bundles with 'bundle--kubehound-attack-' prefix (buggy state)."""
    bundle_ids = get_bundle_ids(data)
    attack_bundles = [bid for bid in bundle_ids if bid.startswith('bundle--kubehound-attack-')]

    assert len(attack_bundles) == 0, \
        f"Found {len(attack_bundles)} bundles with 'bundle--kubehound-attack-' prefix (buggy state): {attack_bundles}"


def test_has_kubehound_attempt_bundles(data):
    """Test that bundles use 'bundle--kubehound-attempt-' prefix (fixed state)."""
    bundle_ids = get_bundle_ids(data)
    attempt_bundles = [bid for bid in bundle_ids if bid.startswith('bundle--kubehound-attempt-')]

    assert len(attempt_bundles) >= 3, \
        f"Expected at least 3 bundles with 'bundle--kubehound-attempt-' prefix, found {len(attempt_bundles)}: {attempt_bundles}"


def test_has_new_bundle_types(data):
    """Test that new bundle types CE_MODULE_LOAD, CE_NET_MITM, CE_VAR_LOG_SYMLINK are present."""
    bundle_ids = get_bundle_ids(data)
    bundle_names = get_bundle_names(data)

    required_bundles = ['CE_MODULE_LOAD', 'CE_NET_MITM', 'CE_VAR_LOG_SYMLINK']

    for required in required_bundles:
        found = required in bundle_names or any(required in bid for bid in bundle_ids)
        assert found, \
            f"Required bundle '{required}' not found. Bundle names: {bundle_names}, IDs: {bundle_ids}"


def test_bundle_count_minimum(data):
    """Test that there are at least 6 bundles (fixed state has 6, buggy has 3)."""
    bundle_ids = get_bundle_ids(data)
    assert len(bundle_ids) >= 6, \
        f"Expected at least 6 bundles, found {len(bundle_ids)}: {bundle_ids}"


def test_description_changes(data):
    """Test that description fields have been updated (e.g., 'Attempted' instead of just description)."""
    # In the fixed version, CE_NSENTER description should contain "Attempted"
    for bundle in data:
        if not isinstance(bundle, dict):
            continue
        bundle_id = bundle.get('id', '')
        if 'CE_NSENTER' in bundle_id and 'attempt' in bundle_id.lower():
            objects = bundle.get('objects', [])
            for obj in objects:
                if obj.get('type') == 'attack-pattern' and obj.get('name') == 'CE_NSENTER':
                    desc = obj.get('description', '')
                    assert 'Attempted' in desc, \
                        f"Expected 'Attempted' in CE_NSENTER description, got: '{desc}'"


def test_json_valid(data):
    """Test that the JSON file has valid syntax and structure."""
    assert isinstance(data, list), "JSON root should be a list"
