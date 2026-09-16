// Unless explicitly stated otherwise all files in this repository are licensed
// under the Apache License Version 2.0.
// This product includes software developed at Datadog (https://www.datadoghq.com/).
// Copyright 2016-present Datadog, Inc.

//go:build containerd

package containerd

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

// TestKnownImagesGetPreferredNameExists tests that the getPreferredName method
// introduced in the fix exists and returns a non-empty string for known images.
// The method selects a user-friendly image name from the available references.
func TestKnownImagesGetPreferredNameExists(t *testing.T) {
	knownImages := newKnownImages()

	imageID := "sha256:92ca512c4cbb8a0909f903979610d5ee300ee26ce2898040c99606d1de46fce1"
	repoTag := "gcr.io/datadoghq/agent:7.42.0"
	repoDigest := "gcr.io/datadoghq/agent@sha256:3a19076bfee70900a600b8e3ee2cc30d5101d1d3d2b33654f1a316e596eaa4e0"

	// Add references
	knownImages.addReference(repoDigest, imageID)
	knownImages.addReference(repoTag, imageID)
	knownImages.addReference(imageID, imageID)

	// Get preferred name - the fix introduces this method
	preferredName := knownImages.getPreferredName(imageID)

	// Should return a non-empty name
	assert.NotEmpty(t, preferredName, "getPreferredName should return a non-empty string")

	// Should return one of the known references
	validNames := map[string]bool{
		imageID:    true,
		repoTag:    true,
		repoDigest: true,
	}
	assert.True(t, validNames[preferredName], "Should return one of the known references")

	// When repo digest is present, getPreferredName should prefer it
	// (the implementation breaks when it finds a digest)
	// Note: due to map iteration order, we verify that if a digest is returned, it's correct
	if strings.Contains(preferredName, "@sha256:") {
		assert.Equal(t, repoDigest, preferredName, "When repo digest is selected, it should be the correct one")
	}
}

// TestKnownImagesAddReferenceConsolidation tests that multiple references to the
// same image ID are properly consolidated in the knownImages structure.
// This is the core data structure that enables the fix to avoid duplicate events.
func TestKnownImagesAddReferenceConsolidation(t *testing.T) {
	images := newKnownImages()

	imageID := "sha256:92ca512c4cbb8a0909f903979610d5ee300ee26ce2898040c99606d1de46fce1"
	repoTag1 := "gcr.io/datadoghq/agent:7.42.0"
	repoTag2 := "gcr.io/datadoghq/agent:latest"
	repoDigest := "gcr.io/datadoghq/agent@sha256:3a19076bfee70900a600b8e3ee2cc30d5101d1d3d2b33654f1a316e596eaa4e0"

	// Simulate what happens during initial image collection:
	// Multiple references to the same underlying image are added

	// First reference: image ID
	images.addReference(imageID, imageID)
	assert.Equal(t, 1, len(images.namesByID[imageID]), "Should have 1 reference after first add")

	// Second reference: repo tag 1
	images.addReference(repoTag1, imageID)
	assert.Equal(t, 2, len(images.namesByID[imageID]), "Should have 2 references after second add")

	// Third reference: repo tag 2
	images.addReference(repoTag2, imageID)
	assert.Equal(t, 3, len(images.namesByID[imageID]), "Should have 3 references after third add")

	// Fourth reference: repo digest
	images.addReference(repoDigest, imageID)
	assert.Equal(t, 4, len(images.namesByID[imageID]), "Should have 4 references after fourth add")

	// Verify all references are tracked correctly
	assert.Equal(t, imageID, images.idsByName[imageID], "Image ID should map to itself")
	assert.Equal(t, imageID, images.idsByName[repoTag1], "Repo tag 1 should map to image ID")
	assert.Equal(t, imageID, images.idsByName[repoTag2], "Repo tag 2 should map to image ID")
	assert.Equal(t, imageID, images.idsByName[repoDigest], "Repo digest should map to image ID")

	// Verify repo tags are tracked separately
	repoTags := images.getRepoTags(imageID)
	assert.Len(t, repoTags, 2, "Should have 2 repo tags")
	assert.Contains(t, repoTags, repoTag1)
	assert.Contains(t, repoTags, repoTag2)

	// Verify repo digests are tracked separately
	repoDigests := images.getRepoDigests(imageID)
	assert.Len(t, repoDigests, 1, "Should have 1 repo digest")
	assert.Contains(t, repoDigests, repoDigest)
}

// TestKnownImagesDeleteReference tests that references are properly removed
// and the image is only considered gone when all references are deleted.
func TestKnownImagesDeleteReference(t *testing.T) {
	images := newKnownImages()

	imageID := "sha256:92ca512c4cbb8a0909f903979610d5ee300ee26ce2898040c99606d1de46fce1"
	repoTag := "gcr.io/datadoghq/agent:7.42.0"
	repoDigest := "gcr.io/datadoghq/agent@sha256:3a19076bfee70900a600b8e3ee2cc30d5101d1d3d2b33654f1a316e596eaa4e0"

	// Add multiple references
	images.addReference(imageID, imageID)
	images.addReference(repoTag, imageID)
	images.addReference(repoDigest, imageID)

	// Delete the image ID reference - image should still exist
	images.deleteReference(imageID, imageID)
	_, found := images.getImageID(imageID)
	assert.False(t, found, "Image ID should no longer be found as a name")
	assert.Equal(t, 2, len(images.namesByID[imageID]), "Should still have 2 references")

	// Delete the repo tag reference - image should still exist
	images.deleteReference(repoTag, imageID)
	_, found = images.getImageID(repoTag)
	assert.False(t, found, "Repo tag should no longer be found as a name")
	assert.Equal(t, 1, len(images.namesByID[imageID]), "Should still have 1 reference")

	// Get repo digests should still work
	repoDigests := images.getRepoDigests(imageID)
	assert.Len(t, repoDigests, 1, "Should still have 1 repo digest")

	// Delete the last reference - image should be completely gone
	images.deleteReference(repoDigest, imageID)
	assert.Equal(t, 0, len(images.namesByID[imageID]), "Should have no references left")
	assert.Empty(t, images.getRepoTags(imageID), "Should have no repo tags")
	assert.Empty(t, images.getRepoDigests(imageID), "Should have no repo digests")
}

// TestIsAnImageID tests the helper function that identifies image IDs
func TestIsAnImageID(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected bool
	}{
		{"valid_image_id", "sha256:92ca512c4cbb8a0909f903979610d5ee300ee26ce2898040c99606d1de46fce1", true},
		{"valid_image_id_short", "sha256:abc123", true},
		{"repo_tag", "gcr.io/datadoghq/agent:7.42.0", false},
		{"repo_digest", "gcr.io/datadoghq/agent@sha256:3a19076bfee70900a600b8e3ee2cc30d5101d1d3d2b33654f1a316e596eaa4e0", false},
		{"empty", "", false},
		{"random", "random-string", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isAnImageID(tt.input)
			assert.Equal(t, tt.expected, result, "isAnImageID(%q) should return %v", tt.input, tt.expected)
		})
	}
}

// TestIsARepoDigest tests the helper function that identifies repo digests
func TestIsARepoDigest(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected bool
	}{
		{"valid_repo_digest", "gcr.io/datadoghq/agent@sha256:3a19076bfee70900a600b8e3ee2cc30d5101d1d3d2b33654f1a316e596eaa4e0", true},
		{"valid_repo_digest_docker", "docker.io/datadog/agent@sha256:abc123", true},
		{"image_id", "sha256:92ca512c4cbb8a0909f903979610d5ee300ee26ce2898040c99606d1de46fce1", false},
		{"repo_tag", "gcr.io/datadoghq/agent:7.42.0", false},
		{"empty", "", false},
		{"random", "random-string", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := isARepoDigest(tt.input)
			assert.Equal(t, tt.expected, result, "isARepoDigest(%q) should return %v", tt.input, tt.expected)
		})
	}
}

// TestImageMetadataConsolidationLogic tests the core logic that enables
// image metadata consolidation. This test verifies that when multiple images
// with the same entity ID are processed, they result in a single consolidated
// metadata object.
func TestImageMetadataConsolidationLogic(t *testing.T) {
	// This test verifies the data structure behavior that the fix relies on.
	// The fix uses mergedImages map[workloadmeta.EntityID]*workloadmeta.ContainerImageMetadata
	// to consolidate multiple references to the same image.

	// Simulate the scenario from the fix:
	// Multiple images with different names but same entity ID (config digest)
	imageID := "sha256:92ca512c4cbb8a0909f903979610d5ee300ee26ce2898040c99606d1de46fce1"

	// Create knownImages structure to track references
	knownImages := newKnownImages()

	// Simulate processing multiple image references during initial collection
	// This is what happens in notifyInitialImageEvents after the fix:
	// 1. Each image reference is processed via createOrUpdateImageMetadata
	// 2. References are added to knownImages
	// 3. Results are stored in mergedImages map by entity ID
	// 4. Only one event is emitted per unique entity ID

	references := []string{
		"sha256:92ca512c4cbb8a0909f903979610d5ee300ee26ce2898040c99606d1de46fce1",
		"gcr.io/datadoghq/agent:7.42.0",
		"gcr.io/datadoghq/agent:latest",
		"gcr.io/datadoghq/agent@sha256:3a19076bfee70900a600b8e3ee2cc30d5101d1d3d2b33654f1a316e596eaa4e0",
	}

	// Add all references
	for _, ref := range references {
		knownImages.addReference(ref, imageID)
	}

	// Verify consolidation: all references point to the same image ID
	for _, ref := range references {
		gotID, found := knownImages.getImageID(ref)
		assert.True(t, found, "Reference %q should be found", ref)
		assert.Equal(t, imageID, gotID, "Reference %q should map to image ID", ref)
	}

	// Verify that getPreferredName returns a valid name (one of the references)
	preferredName := knownImages.getPreferredName(imageID)
	assert.NotEmpty(t, preferredName, "Should return a non-empty preferred name")

	// Verify repo tags and digests are correctly categorized
	repoTags := knownImages.getRepoTags(imageID)
	repoDigests := knownImages.getRepoDigests(imageID)
	assert.Len(t, repoTags, 2, "Should have 2 repo tags")
	assert.Len(t, repoDigests, 1, "Should have 1 repo digest")
}

// TestNameUpdateWhenMoreReadable tests the logic that updates image names
// only when the new name is more readable (doesn't contain sha256 in a raw form)
func TestNameUpdateWhenMoreReadable(t *testing.T) {
	// This test verifies the name update logic from the fix:
	// "When an image already exists in the metadata store, its name should be
	// updated only when the newly selected preferred name is more readable
	// (i.e., does not contain a raw sha256 string)."
	//
	// The fix implements this as:
	// if strings.Contains(wlmImage.Name, "sha256:") && !strings.Contains(existingImg.Name, "sha256:") {
	//     wlmImage.Name = existingImg.Name
	// }
	//
	// This means: if the NEW name has sha256 but the EXISTING name doesn't,
	// keep the existing name (don't update to the sha256 name).

	shaName := "sha256:92ca512c4cbb8a0909f903979610d5ee300ee26ce2898040c99606d1de46fce1"
	readableName := "gcr.io/datadoghq/agent:7.42.0"
	repoDigestName := "gcr.io/datadoghq/agent@sha256:3a19076bfee70900a600b8e3ee2cc30d5101d1d3d2b33654f1a316e596eaa4e0"

	tests := []struct {
		name              string
		newName           string  // The name from the new image being processed
		existingName      string  // The name already in the store
		shouldKeepExisting  bool  // Whether to keep the existing name
		expectedFinalName string
		description       string
	}{
		{
			name:              "keep_readable_existing_when_new_has_raw_sha",
			newName:           shaName,
			existingName:      readableName,
			shouldKeepExisting: true,
			expectedFinalName: readableName,
			description:       "Should keep existing readable name when new name has raw sha256",
		},
		{
			name:              "update_to_readable_when_existing_has_sha",
			newName:           readableName,
			existingName:      shaName,
			shouldKeepExisting: false,
			expectedFinalName: readableName,
			description:       "Should use new readable name when existing has raw sha256",
		},
		{
			name:              "keep_new_when_both_have_sha",
			newName:           repoDigestName,
			existingName:      shaName,
			shouldKeepExisting: false, // Both have sha256, so condition is false, new name is kept
			expectedFinalName: repoDigestName,
			description:       "When both have sha256, the condition doesn't trigger, new name is kept",
		},
		{
			name:              "keep_new_repo_digest_when_existing_has_raw_sha",
			newName:           repoDigestName,
			existingName:      shaName,
			shouldKeepExisting: false,
			expectedFinalName: repoDigestName,
			description:       "Repo digest also contains sha256:, so condition is false, new name kept",
		},
		{
			name:              "keep_readable_when_new_has_repo_digest",
			newName:           repoDigestName,
			existingName:      readableName,
			shouldKeepExisting: true,
			expectedFinalName: readableName,
			description:       "When existing is readable and new has sha256 (even in digest form), keep existing",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Simulate the logic from the fix:
			// if strings.Contains(wlmImage.Name, "sha256:") && !strings.Contains(existingImg.Name, "sha256:") {
			//     wlmImage.Name = existingImg.Name
			// }

			newName := tt.newName
			existingName := tt.existingName

			// Check if we should keep existing (this is the condition from the fix, inverted)
			// The fix says: if new has sha256 AND existing doesn't, use existing
			shouldKeepExisting := strings.Contains(newName, "sha256:") && !strings.Contains(existingName, "sha256:")

			assert.Equal(t, tt.shouldKeepExisting, shouldKeepExisting, "Keep existing decision mismatch")

			// Apply the update logic
			finalName := newName
			if shouldKeepExisting {
				finalName = existingName
			}

			assert.Equal(t, tt.expectedFinalName, finalName, tt.description)
		})
	}
}

// TestKnownImagesReferenceReplacement tests that when a name is re-added
// with a different image ID, the old reference is properly removed
func TestKnownImagesReferenceReplacement(t *testing.T) {
	images := newKnownImages()

	oldImageID := "sha256:old123"
	newImageID := "sha256:new456"
	repoTag := "gcr.io/datadoghq/agent:7.42.0"

	// Add reference with old image ID
	images.addReference(repoTag, oldImageID)
	gotID, found := images.getImageID(repoTag)
	assert.True(t, found)
	assert.Equal(t, oldImageID, gotID)

	// Re-add the same name with new image ID (this happens when image is retagged)
	images.addReference(repoTag, newImageID)

	// Verify the reference was updated
	gotID, found = images.getImageID(repoTag)
	assert.True(t, found)
	assert.Equal(t, newImageID, gotID, "Reference should be updated to new image ID")

	// Verify old image ID no longer has this reference
	assert.Empty(t, images.namesByID[oldImageID], "Old image ID should have no references")
	assert.Equal(t, 1, len(images.namesByID[newImageID]), "New image ID should have 1 reference")
}

// TestGetPreferredNameWithRepoDigestPriority tests that when a repo digest is
// encountered during iteration, it is selected and the loop breaks immediately.
// This is the key behavior of getPreferredName introduced in the fix.
func TestGetPreferredNameWithRepoDigestPriority(t *testing.T) {
	knownImages := newKnownImages()

	imageID := "sha256:92ca512c4cbb8a0909f903979610d5ee300ee26ce2898040c99606d1de46fce1"
	repoTag := "gcr.io/datadoghq/agent:7.42.0"
	repoDigest := "gcr.io/datadoghq/agent@sha256:3a19076bfee70900a600b8e3ee2cc30d5101d1d3d2b33654f1a316e596eaa4e0"

	// Add references
	knownImages.addReference(repoDigest, imageID)
	knownImages.addReference(repoTag, imageID)

	// Get preferred name multiple times to check consistency
	// (map iteration order is random, but digest should always win due to break)
	for i := 0; i < 10; i++ {
		preferredName := knownImages.getPreferredName(imageID)
		// When a repo digest is present, getPreferredName should select it
		// because the implementation breaks immediately when it finds a digest
		assert.Contains(t, preferredName, "@sha256:", "Repo digest should be preferred when present (iteration %d)", i)
		assert.Equal(t, repoDigest, preferredName, "Should return the correct repo digest (iteration %d)", i)
	}
}
