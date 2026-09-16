# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""
Quick smoke test for ST_S2ToGeom function availability.

This test verifies that the ST_S2ToGeom function is properly exposed
in the Python API without requiring a full Spark session.
"""

import pytest


def test_st_s2_to_geom_import():
    """Test that ST_S2ToGeom can be imported from sedona.sql.st_functions."""
    from sedona.sql.st_functions import ST_S2ToGeom
    assert ST_S2ToGeom is not None, "ST_S2ToGeom should be importable"
    assert callable(ST_S2ToGeom), "ST_S2ToGeom should be callable"


def test_st_s2_to_geom_in_exports():
    """Test that ST_S2ToGeom is in the module's __all__ exports."""
    from sedona.sql import st_functions
    assert "ST_S2ToGeom" in st_functions.__all__, "ST_S2ToGeom should be in __all__"


def test_st_s2_to_geom_signature():
    """Test that ST_S2ToGeom has the expected function signature."""
    from sedona.sql.st_functions import ST_S2ToGeom
    import inspect
    sig = inspect.signature(ST_S2ToGeom)
    params = list(sig.parameters.keys())
    assert "cells" in params, "ST_S2ToGeom should have 'cells' parameter"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
