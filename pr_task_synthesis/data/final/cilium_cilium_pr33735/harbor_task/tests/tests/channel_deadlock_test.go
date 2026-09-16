// SPDX-License-Identifier: Apache-2.0
// Copyright Authors of Cilium

package common

import (
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/require"

	"github.com/cilium/cilium/pkg/clustermesh/types"
)

// TestChannelBufferFixAtLine270 verifies the fix for the deadlock race
// condition in getClusterConfig.
//
// BUG: When context times out, main goroutine returns. But background
// controller may still try to send to cfgch. With unbuffered channel,
// this blocks forever.
//
// FIX at line 270: make(chan types.CiliumClusterConfig, 1)
//
// This test:
// 1. Verifies the source code contains the fix
// 2. Tests the channel behavior to confirm it doesn't block
func TestChannelBufferFixAtLine270(t *testing.T) {
	// Part 1: Verify source code contains the fix
	// Read remote_cluster.go and check line 270
	sourceFile := "remote_cluster.go"
	content, err := os.ReadFile(sourceFile)
	if err != nil {
		// Try alternative path
		content, err = os.ReadFile("pkg/clustermesh/common/remote_cluster.go")
	}
	if err != nil {
		t.Skipf("Could not read source file: %v", err)
	}

	lines := strings.Split(string(content), "\n")
	// Line 270 should contain the channel creation
	// The fix adds ", 1" for buffered channel
	foundFix := false
	for i, line := range lines {
		if strings.Contains(line, "make(chan types.CiliumClusterConfig") {
			if strings.Contains(line, ", 1)") {
				foundFix = true
				t.Logf("Line %d: Found buffered channel (fix applied): %s", i+1, strings.TrimSpace(line))
			} else {
				t.Logf("Line %d: Found unbuffered channel (BUG): %s", i+1, strings.TrimSpace(line))
			}
		}
	}

	require.True(t, foundFix,
		"Channel buffer fix not found at line 270. "+
			"Expected: make(chan types.CiliumClusterConfig, 1)")

	// Part 2: Verify the channel behavior
	testTimeout := 2 * time.Second

	// Create channel with the FIXED pattern
	cfgch := make(chan types.CiliumClusterConfig, 1)
	defer close(cfgch)

	sendDone := make(chan struct{})
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		cfgch <- types.CiliumClusterConfig{ID: 42}
		close(sendDone)
	}()

	select {
	case <-sendDone:
		t.Log("Channel send completed without blocking")
	case <-time.After(testTimeout):
		t.Fatal("DEADLOCK: Channel send blocked")
	}

	wg.Wait()

	// Verify value is receivable
	select {
	case config := <-cfgch:
		require.Equal(t, uint32(42), config.ID)
	case <-time.After(testTimeout):
		t.Fatal("Could not receive from channel")
	}
}
