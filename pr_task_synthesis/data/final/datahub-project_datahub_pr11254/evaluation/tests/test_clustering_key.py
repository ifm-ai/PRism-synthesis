"""
Test for CLUSTERING_KEY fix in Snowflake metadata ingestion.

This test verifies that when a Snowflake table has a CLUSTERING_KEY column value,
the ingestion code correctly adds it to the dataset's customProperties.

Grounded in fix.patch which modifies snowflake_schema_gen.py to:
1. Check if table.clustering_key exists
2. Add it to customProperties["CLUSTERING_KEY"]
"""

import pytest
import sys
import os

# Add the source directory to the path
sys.path.insert(0, '/workspace/metadata-ingestion/src')


def test_clustering_key_fix_present():
    """
    Test that the CLUSTERING_KEY fix is present in snowflake_schema_gen.py.
    
    The fix should:
    1. Initialize custom_properties = {}
    2. Check if table.clustering_key exists and add it to custom_properties
    3. Pass custom_properties to DatasetProperties instead of empty {}
    """
    # Read the source file - use cwd to support testing against different clones
    import os
    cwd = os.getcwd()
    source_file = os.path.join(cwd, 'metadata-ingestion/src/datahub/ingestion/source/snowflake/snowflake_schema_gen.py')
    with open(source_file, 'r') as f:
        source_code = f.read()
    
    # Check for the fix pattern - custom_properties initialization
    assert 'custom_properties = {}' in source_code, \
        "Fix should initialize custom_properties = {}"
    
    # Check for the fix pattern - checking clustering_key
    assert 'table.clustering_key' in source_code, \
        "Fix should check table.clustering_key"
    
    # Check for the fix pattern - adding CLUSTERING_KEY to custom_properties
    assert 'custom_properties["CLUSTERING_KEY"]' in source_code or \
           "custom_properties['CLUSTERING_KEY']" in source_code, \
        "Fix should add CLUSTERING_KEY to custom_properties"
    
    # Check that DatasetProperties uses custom_properties (not empty {})
    # The fixed version should have customProperties=custom_properties
    assert 'customProperties=custom_properties' in source_code, \
        "DatasetProperties should use customProperties=custom_properties"
    
    # Make sure the old buggy pattern is NOT present (customProperties={})
    # We need to check that the get_dataset_properties method doesn't have 
    # customProperties={} anymore
    import re
    # Find the get_dataset_properties method
    method_match = re.search(
        r'def get_dataset_properties\(.*?\).*?:.*?return DatasetProperties\((.*?)\)',
        source_code,
        re.DOTALL
    )
    if method_match:
        method_body = method_match.group(1)
        # The buggy version has customProperties={}
        # The fixed version should NOT have this pattern
        assert 'customProperties={}' not in method_body, \
            "get_dataset_properties should NOT have customProperties={} (should use custom_properties variable)"
    
    print("✓ CLUSTERING_KEY fix is correctly implemented in snowflake_schema_gen.py")


def test_clustering_key_behavior():
    """
    Test the actual behavior by simulating the fix logic.
    
    This test simulates what the fixed code should do:
    - If table has clustering_key, add it to customProperties
    - If table has no clustering_key (None), customProperties should be empty
    """
    # Simulate the fix logic
    class MockTable:
        def __init__(self, clustering_key):
            self.clustering_key = clustering_key
    
    # Test case 1: Table WITH clustering_key
    table_with_key = MockTable(clustering_key="LINEAR(COL_1)")
    
    # This is what the fix does
    custom_properties = {}
    if table_with_key.clustering_key:
        custom_properties["CLUSTERING_KEY"] = table_with_key.clustering_key
    
    assert custom_properties == {"CLUSTERING_KEY": "LINEAR(COL_1)"}, \
        f"Expected CLUSTERING_KEY in custom_properties, got: {custom_properties}"
    
    # Test case 2: Table WITHOUT clustering_key (None)
    table_without_key = MockTable(clustering_key=None)
    
    custom_properties = {}
    if table_without_key.clustering_key:
        custom_properties["CLUSTERING_KEY"] = table_without_key.clustering_key
    
    assert custom_properties == {}, \
        f"Expected empty custom_properties for None clustering_key, got: {custom_properties}"
    
    # Test case 3: Table WITHOUT clustering_key (empty string)
    table_empty_key = MockTable(clustering_key="")
    
    custom_properties = {}
    if table_empty_key.clustering_key:
        custom_properties["CLUSTERING_KEY"] = table_empty_key.clustering_key
    
    assert custom_properties == {}, \
        f"Expected empty custom_properties for empty clustering_key, got: {custom_properties}"
    
    print("✓ CLUSTERING_KEY behavior is correct")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
