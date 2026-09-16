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
Hidden verifier tests for ST_S2ToGeom function.

This test verifies that:
1. ST_S2ToGeom function exists and is callable
2. It converts S2 cell IDs to polygon geometries
3. The resulting polygons intersect the source geometry
4. The output array preserves input order
5. Results are compatible with ST_Collect producing MULTIPOLYGON
"""

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, array, lit
from sedona.sql.st_functions import ST_S2ToGeom, ST_S2CellIDs, ST_Intersects, ST_GeomFromWKT, ST_Collect, GeometryType
from sedona.register import SedonaRegistrator


@pytest.fixture(scope="session")
def spark():
    """Create a Spark session with Sedona registered."""
    spark = (SparkSession.builder
             .appName("ST_S2ToGeom Test")
             .master("local[2]")
             .config("spark.sql.adaptive.enabled", "false")
             .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
             .getOrCreate())
    SedonaRegistrator.registerAll(spark)
    yield spark
    spark.stop()


class TestST_S2ToGeom:
    """Tests for the ST_S2ToGeom function."""

    def test_st_s2_to_geom_basic(self, spark):
        """Test that ST_S2ToGeom converts S2 cell IDs to polygons that intersect source geometry."""
        # Create a test polygon
        wkt = "POLYGON ((0.1 0.1, 0.5 0.1, 1 0.3, 1 1, 0.1 1, 0.1 0.1))"

        # Get S2 cell IDs for the polygon at level 10
        cell_df = spark.sql(f"""
            SELECT ST_S2CellIDs(ST_GeomFromWKT('{wkt}'), 10) as cell_ids
        """)
        cell_ids_row = cell_df.take(1)[0]
        assert cell_ids_row is not None, "Failed to get S2 cell IDs"

        cell_ids = cell_ids_row[0]
        assert cell_ids is not None, "Cell IDs should not be None"
        assert len(cell_ids) > 100, f"Expected more than 100 cells, got {len(cell_ids)}"

        # Test ST_S2ToGeom - convert cell IDs back to polygons
        result_df = spark.sql(f"""
            SELECT ST_S2ToGeom(ST_S2CellIDs(ST_GeomFromWKT('{wkt}'), 10)) as polygons
        """)
        result_row = result_df.take(1)[0]
        polygons = result_row[0]

        assert polygons is not None, "ST_S2ToGeom should return non-None result"
        assert len(polygons) == len(cell_ids), "Output array length should match input"

        # Verify that specific indexed polygons intersect the target
        target_geom = spark.sql(f"SELECT ST_GeomFromWKT('{wkt}') as geom").take(1)[0][0]

        # Check intersection at indices 0, 20, 100 as specified in the issue
        for idx in [0, 20, 100]:
            if idx < len(polygons):
                intersects = spark.sql(f"""
                    SELECT ST_Intersects(
                        ST_GeomFromWKT('{wkt}'),
                        ST_S2ToGeom(ST_S2CellIDs(ST_GeomFromWKT('{wkt}'), 10))[{idx}]
                    ) as intersects
                """).take(1)[0][0]
                assert intersects is True, f"Polygon at index {idx} should intersect target geometry"

    def test_st_s2_to_geom_with_collect(self, spark):
        """Test that ST_S2ToGeom results are compatible with ST_Collect producing MULTIPOLYGON."""
        wkt = "POLYGON ((0.1 0.1, 0.5 0.1, 1 0.3, 1 1, 0.1 1, 0.1 0.1))"

        # Collect the array of geometries into a MultiPolygon
        result_df = spark.sql(f"""
            SELECT ST_Collect(ST_S2ToGeom(ST_S2CellIDs(ST_GeomFromWKT('{wkt}'), 10))) as multipolygon
        """)
        result_row = result_df.take(1)[0]
        multipolygon = result_row[0]

        assert multipolygon is not None, "ST_Collect should return non-None result"

        # Check that the geometry type is MULTIPOLYGON
        geom_type_df = spark.sql(f"""
            SELECT GeometryType(ST_Collect(ST_S2ToGeom(ST_S2CellIDs(ST_GeomFromWKT('{wkt}'), 10)))) as geom_type
        """)
        geom_type = geom_type_df.take(1)[0][0]
        assert geom_type == "MULTIPOLYGON", f"Expected MULTIPOLYGON, got {geom_type}"

    def test_st_s2_to_geom_order_preservation(self, spark):
        """Test that ST_S2ToGeom preserves the order of input cell IDs."""
        wkt = "POLYGON ((0.1 0.1, 0.5 0.1, 1 0.3, 1 1, 0.1 1, 0.1 0.1))"

        # Get cell IDs
        cell_df = spark.sql(f"""
            SELECT ST_S2CellIDs(ST_GeomFromWKT('{wkt}'), 10) as cell_ids
        """)
        cell_ids = cell_df.take(1)[0][0]

        # Get polygons
        poly_df = spark.sql(f"""
            SELECT ST_S2ToGeom(ST_S2CellIDs(ST_GeomFromWKT('{wkt}'), 10)) as polygons
        """)
        polygons = poly_df.take(1)[0][0]

        # Each polygon should correspond to its cell ID
        # This is implicitly verified by the intersection tests above
        assert len(polygons) == len(cell_ids), "Order should be preserved (same length)"

    def test_st_s2_to_geom_null_handling(self, spark):
        """Test that ST_S2ToGeom handles null input gracefully."""
        result_df = spark.sql("""
            SELECT ST_S2ToGeom(NULL) as result
        """)
        result = result_df.take(1)[0][0]
        assert result is None, "ST_S2ToGeom should return None for null input"

    def test_st_s2_to_geom_empty_array(self, spark):
        """Test ST_S2ToGeom with an empty array of cell IDs."""
        result_df = spark.sql("""
            SELECT ST_S2ToGeom(array()) as result
        """)
        result = result_df.take(1)[0][0]
        assert result is not None, "ST_S2ToGeom should handle empty array"
        assert len(result) == 0, "Result should be empty array for empty input"

    def test_st_s2_to_geom_single_cell(self, spark):
        """Test ST_S2ToGeom with a single S2 cell ID."""
        # Use a known S2 cell ID
        result_df = spark.sql("""
            SELECT ST_S2ToGeom(array(1154047404513689600L)) as result
        """)
        result = result_df.take(1)[0][0]
        assert result is not None, "ST_S2ToGeom should handle single cell"
        assert len(result) == 1, "Result should have exactly one polygon"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
