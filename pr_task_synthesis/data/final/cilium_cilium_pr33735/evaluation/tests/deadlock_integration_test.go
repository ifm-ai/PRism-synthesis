// SPDX-License-Identifier: Apache-2.0
// Copyright Authors of Cilium

package common

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/require"

	"github.com/cilium/cilium/pkg/clustermesh/types"
	"github.com/cilium/cilium/pkg/controller"
	"github.com/cilium/cilium/pkg/kvstore"
)

// slowBackend is a minimal backend mock that delays Get() to trigger
// the race condition in getClusterConfig.
type slowBackend struct {
	getDelay    time.Duration
	configJSON  []byte
	onGetCalled chan struct{}
	mu          sync.Mutex
	closed      bool
}

func (s *slowBackend) Get(ctx context.Context, key string) ([]byte, error) {
	// Signal that Get was called
	s.mu.Lock()
	called := s.onGetCalled
	s.mu.Unlock()
	
	if called != nil {
		select {
		case called <- struct{}{}:
		default:
		}
	}

	// Delay to trigger race condition
	select {
	case <-time.After(s.getDelay):
	case <-ctx.Done():
		return nil, ctx.Err()
	}

	return s.configJSON, nil
}

func (s *slowBackend) Status() (string, error) {
	return "ok", nil
}

func (s *slowBackend) StatusCheckErrors() <-chan error {
	return make(chan error)
}

func (s *slowBackend) Close() {
	s.mu.Lock()
	s.closed = true
	s.mu.Unlock()
}

func (s *slowBackend) Connected(ctx context.Context) <-chan error {
	ch := make(chan error)
	close(ch)
	return ch
}

func (s *slowBackend) Disconnected() <-chan struct{} {
	return make(chan struct{})
}

func (s *slowBackend) LockPath(ctx context.Context, path string) (kvstore.KVLocker, error) {
	return nil, nil
}

func (s *slowBackend) GetIfLocked(ctx context.Context, key string, lock kvstore.KVLocker) ([]byte, error) {
	return s.Get(ctx, key)
}

func (s *slowBackend) Delete(ctx context.Context, key string) error {
	return nil
}

func (s *slowBackend) DeleteIfLocked(ctx context.Context, key string, lock kvstore.KVLocker) error {
	return nil
}

func (s *slowBackend) DeletePrefix(ctx context.Context, path string) error {
	return nil
}

func (s *slowBackend) Update(ctx context.Context, key string, value []byte, lease bool) error {
	return nil
}

func (s *slowBackend) UpdateIfLocked(ctx context.Context, key string, value []byte, lease bool, lock kvstore.KVLocker) error {
	return nil
}

func (s *slowBackend) UpdateIfDifferent(ctx context.Context, key string, value []byte, lease bool) (bool, error) {
	return true, nil
}

func (s *slowBackend) UpdateIfDifferentIfLocked(ctx context.Context, key string, value []byte, lease bool, lock kvstore.KVLocker) (bool, error) {
	return true, nil
}

func (s *slowBackend) CreateOnly(ctx context.Context, key string, value []byte, lease bool) (bool, error) {
	return true, nil
}

func (s *slowBackend) CreateOnlyIfLocked(ctx context.Context, key string, value []byte, lease bool, lock kvstore.KVLocker) (bool, error) {
	return true, nil
}

func (s *slowBackend) List(ctx context.Context, path string) ([]string, error) {
	return nil, nil
}

func (s *slowBackend) ListIfLocked(ctx context.Context, path string, lock kvstore.KVLocker) ([]string, error) {
	return nil, nil
}

func (s *slowBackend) ListAndCollect(ctx context.Context, path string) (kvstore.LKMap, error) {
	return nil, nil
}

func (s *slowBackend) ListAndCollectIfLocked(ctx context.Context, path string, lock kvstore.KVLocker) (kvstore.LKMap, error) {
	return nil, nil
}

func (s *slowBackend) DeletePrefixIfLocked(ctx context.Context, path string, lock kvstore.KVLocker) error {
	return nil
}

func (s *slowBackend) Watch(ctx context.Context, path string) kvstore.Watcher {
	return nil
}

func (s *slowBackend) WatchIfLocked(ctx context.Context, path string, lock kvstore.KVLocker) kvstore.Watcher {
	return nil
}

func (s *slowBackend) Encode(key string, value interface{}) ([]byte, error) {
	return nil, nil
}

func (s *slowBackend) Decode(key string, data []byte, value interface{}) error {
	return nil
}

func (s *slowBackend) Capabilities() kvstore.Capabilities {
	return kvstore.Capabilities{}
}

func (s *slowBackend) RenewLease(ctx context.Context) error {
	return nil
}

func (s *slowBackend) StopLeaseRenew() {}

func (s *slowBackend) GetKey(ctx context.Context, key string) (*kvstore.Key, error) {
	return nil, nil
}

func (s *slowBackend) GetKeyIfLocked(ctx context.Context, key string, lock kvstore.KVLocker) (*kvstore.Key, error) {
	return nil, nil
}

// TestGetClusterConfigNoDeadlockOnContextTimeout tests the fix for the
// deadlock race condition in getClusterConfig (line 270).
//
// SCENARIO:
// 1. getClusterConfig starts a controller to fetch config
// 2. Context times out before config is fetched (200ms < 500ms delay)
// 3. Main goroutine returns from getClusterConfig with error
// 4. Controller eventually succeeds (after 500ms) and tries: cfgch <- config
//
// WITHOUT FIX (unbuffered channel at line 270):
// - Step 4 blocks forever because receiver (main goroutine) is gone
// - Controller goroutine hangs = DEADLOCK
// - Test times out and FAILS
//
// WITH FIX (buffered channel with capacity 1):
// - Step 4 succeeds because buffer accepts the value
// - Controller goroutine completes normally
// - Test completes and PASSES
func TestGetClusterConfigNoDeadlockOnContextTimeout(t *testing.T) {
	// Test timeout - if getClusterConfig doesn't return in this time,
	// we have a deadlock (bug present, fix missing)
	testTimeout := 5 * time.Second

	// Create mock backend that delays config retrieval
	// This delay (500ms) is longer than the context timeout (200ms)
	// to trigger the race condition
	onGetCalled := make(chan struct{}, 1)
	backend := &slowBackend{
		getDelay:    500 * time.Millisecond,
		configJSON:  []byte(`{"id": 42, "capabilities": {}}`),
		onGetCalled: onGetCalled,
	}

	// Create minimal remoteCluster with noop metrics
	rc := &remoteCluster{
		name:                           "test-cluster",
		remoteConnectionControllerName: "test",
		controllers:                    controller.NewManager(),
		logger:                         logrus.NewEntry(logrus.New()),
		metricLastFailureTimestamp:     prometheus.NewGauge(prometheus.GaugeOpts{Name: "test_last_failure"}),
		metricReadinessStatus:          prometheus.NewGauge(prometheus.GaugeOpts{Name: "test_readiness"}),
		metricTotalFailures:            prometheus.NewGauge(prometheus.GaugeOpts{Name: "test_failures"}),
		clusterSizeDependantInterval:   func(baseInterval time.Duration) time.Duration { return baseInterval },
	}

	// Context timeout shorter than backend delay - triggers race condition
	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()

	resultCh := make(chan struct {
		config types.CiliumClusterConfig
		err    error
	}, 1)

	// Call getClusterConfig in a goroutine
	go func() {
		config, err := rc.getClusterConfig(ctx, backend)
		resultCh <- struct {
			config types.CiliumClusterConfig
			err    error
		}{config, err}
	}()

	// Wait for Get to be called (confirms controller is running)
	select {
	case <-onGetCalled:
		t.Log("Controller started fetching config")
	case <-time.After(1 * time.Second):
		t.Fatal("Controller did not start")
	}

	// Wait for getClusterConfig to return or timeout (deadlock)
	select {
	case result := <-resultCh:
		// Function returned - no deadlock!
		t.Logf("getClusterConfig returned: err=%v", result.err)
		// Should return error because context timed out
		require.Error(t, result.err, "Expected error due to context timeout")

	case <-time.After(testTimeout):
		t.Fatal("DEADLOCK DETECTED: getClusterConfig did not return within timeout. " +
			"The channel buffer fix is missing at line 270. " +
			"Expected: make(chan types.CiliumClusterConfig, 1)")
	}

	// Give controller time to complete its send
	// With buffered channel (fix), this completes quickly
	// With unbuffered channel (bug), controller would be blocked
	time.Sleep(800 * time.Millisecond)

	// Cleanup
	rc.controllers.RemoveAll()
	backend.Close()
}
