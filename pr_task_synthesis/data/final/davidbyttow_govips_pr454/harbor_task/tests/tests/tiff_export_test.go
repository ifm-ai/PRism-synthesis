package vips_test

import (
	"testing"

	govips "github.com/davidbyttow/govips/v2/vips"
	"github.com/stretchr/testify/assert"
)

// TestTiffExportParams_HasPyramidField verifies that TiffExportParams has Pyramid field
// This test will fail to compile without the fix because Pyramid field doesn't exist
func TestTiffExportParams_HasPyramidField(t *testing.T) {
	govips.Startup(&govips.Config{})

	// Create params and set Pyramid field - this requires the fix to compile
	params := govips.NewTiffExportParams()
	params.Pyramid = true

	// Verify the field is accessible and set correctly
	assert.True(t, params.Pyramid, "Pyramid field should be settable to true")
}

// TestTiffExportParams_HasTileField verifies that TiffExportParams has Tile field
// This test will fail to compile without the fix because Tile field doesn't exist
func TestTiffExportParams_HasTileField(t *testing.T) {
	govips.Startup(&govips.Config{})

	// Create params and set Tile field - this requires the fix to compile
	params := govips.NewTiffExportParams()
	params.Tile = true

	// Verify the field is accessible and set correctly
	assert.True(t, params.Tile, "Tile field should be settable to true")
}

// TestTiffExportParams_HasTileDimensions verifies that TiffExportParams has TileHeight and TileWidth fields
// This test will fail to compile without the fix because these fields don't exist
func TestTiffExportParams_HasTileDimensions(t *testing.T) {
	govips.Startup(&govips.Config{})

	// Create params and set tile dimension fields - this requires the fix to compile
	params := govips.NewTiffExportParams()
	params.TileHeight = 512
	params.TileWidth = 512

	// Verify the fields are accessible and set correctly
	assert.Equal(t, 512, params.TileHeight, "TileHeight should be settable to 512")
	assert.Equal(t, 512, params.TileWidth, "TileWidth should be settable to 512")
}

// TestTiffExportParams_DefaultValues verifies that NewTiffExportParams sets correct defaults
// The fix adds Pyramid=false, Tile=false, TileHeight=256, TileWidth=256 as defaults
func TestTiffExportParams_DefaultValues(t *testing.T) {
	govips.Startup(&govips.Config{})

	params := govips.NewTiffExportParams()

	// Verify default values for the new fields added by the fix
	assert.False(t, params.Pyramid, "Pyramid should default to false")
	assert.False(t, params.Tile, "Tile should default to false")
	assert.Equal(t, 256, params.TileHeight, "TileHeight should default to 256")
	assert.Equal(t, 256, params.TileWidth, "TileWidth should default to 256")
}

// TestTiffExportParams_AllFieldsTogether verifies all new fields can be used together
func TestTiffExportParams_AllFieldsTogether(t *testing.T) {
	govips.Startup(&govips.Config{})

	// Create params with all new fields set - this requires the fix to compile
	params := &govips.TiffExportParams{
		Pyramid:    true,
		Tile:       true,
		TileHeight: 512,
		TileWidth:  1024,
		Quality:    90,
	}

	assert.True(t, params.Pyramid, "Pyramid should be true")
	assert.True(t, params.Tile, "Tile should be true")
	assert.Equal(t, 512, params.TileHeight, "TileHeight should be 512")
	assert.Equal(t, 1024, params.TileWidth, "TileWidth should be 1024")
	assert.Equal(t, 90, params.Quality, "Quality should be 90")
}
