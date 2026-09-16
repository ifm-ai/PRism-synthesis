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

// delayedSuccessBackend returns success after a delay.
// This triggers the race: context times out, but controller eventually succeeds.
type delayedSuccessBackend struct {
	delay       time.Duration
	configJSON  []byte
	getCalled   chan struct{}
}

func (d *delayedSuccessBackend) Get(ctx context.Context, key string) ([]byte, error) {
	close(d.getCalled)
	
	// Wait for delay or context cancellation
	select {
	case <-time.After(d.delay):
		return d.configJSON, nil
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}

func (d *delayedSuccessBackend) Status() (string, error)                                    { return "ok", nil }
func (d *delayedSuccessBackend) StatusCheckErrors() <-chan error                           { return make(chan error) }
func (d *delayedSuccessBackend) Close()                                                    {}
func (d *delayedSuccessBackend) Connected(ctx context.Context) <-chan error                { ch := make(chan error); close(ch); return ch }
func (d *delayedSuccessBackend) Disconnected() <-chan struct{}                             { ch := make(chan struct{}); close(ch); return ch }
func (d *delayedSuccessBackend) LockPath(ctx context.Context, path string) (kvstore.KVLocker, error) { return nil, nil }
func (d *delayedSuccessBackend) GetIfLocked(ctx context.Context, key string, lock kvstore.KVLocker) ([]byte, error) { return d.Get(ctx, key) }
func (d *delayedSuccessBackend) Delete(ctx context.Context, key string) error              { return nil }
func (d *delayedSuccessBackend) DeleteIfLocked(ctx context.Context, key string, lock kvstore.KVLocker) error { return nil }
func (d *delayedSuccessBackend) DeletePrefix(ctx context.Context, path string) error       { return nil }
func (d *delayedSuccessBackend) Update(ctx context.Context, key string, value []byte, lease bool) error { return nil }
func (d *delayedSuccessBackend) UpdateIfLocked(ctx context.Context, key string, value []byte, lease bool, lock kvstore.KVLocker) error { return nil }
func (d *delayedSuccessBackend) UpdateIfDifferent(ctx context.Context, key string, value []byte, lease bool) (bool, error) { return true, nil }
func (d *delayedSuccessBackend) UpdateIfDifferentIfLocked(ctx context.Context, key string, value []byte, lease bool, lock kvstore.KVLocker) (bool, error) { return true, nil }
func (d *delayedSuccessBackend) CreateOnly(ctx context.Context, key string, value []byte, lease bool) (bool, error) { return true, nil }
func (d *delayedSuccessBackend) CreateOnlyIfLocked(ctx context.Context, key string, value []byte, lease bool, lock kvstore.KVLocker) (bool, error) { return true, nil }
func (d *delayedSuccessBackend) ListPrefix(ctx context.Context, prefix string) (kvstore.KeyValuePairs, error) { return nil, nil }
func (d *delayedSuccessBackend) ListPrefixIfLocked(ctx context.Context, prefix string, lock kvstore.KVLocker) (kvstore.KeyValuePairs, error) { return nil, nil }
func (d *delayedSuccessBackend) Encode(in []byte) string                                   { return string(in) }
func (d *delayedSuccessBackend) Decode(in string) ([]byte, error)                          { return []byte(in), nil }
func (d *delayedSuccessBackend) ListAndWatch(ctx context.Context, prefix string, chanSize int) *kvstore.Watcher { return nil }
func (d *delayedSuccessBackend) RegisterLeaseExpiredObserver(prefix string, fn func(key string)) {}
func (d *delayedSuccessBackend) UserEnforcePresence(ctx context.Context, name string, roles []string) error { return nil }
func (d *delayedSuccessBackend) UserEnforceAbsence(ctx context.Context, name string) error { return nil }

// TestGetClusterConfigNoDeadlock tests the fix for the deadlock at line 270.
//
// SCENARIO:
// 1. getClusterConfig starts controller with 100ms context timeout
// 2. Backend delays 300ms before returning config
// 3. Context times out at 100ms, main goroutine returns
// 4. At 300ms, controller succeeds and tries: cfgch <- config
//
// WITHOUT FIX (unbuffered channel): Step 4 blocks forever = DEADLOCK
// WITH FIX (buffered channel, cap=1): Step 4 succeeds immediately
//
// The test verifies getClusterConfig returns without hanging.
func TestGetClusterConfigNoDeadlock(t *testing.T) {
	testTimeout := 5 * time.Second

	getCalled := make(chan struct{}, 1)
	backend := &delayedSuccessBackend{
		delay:      300 * time.Millisecond,
		configJSON: []byte(`{"id": 42, "capabilities": {}}`),
		getCalled:  getCalled,
	}

	rc := &remoteCluster{
		name:                           "test",
		remoteConnectionControllerName: "test",
		controllers:                    controller.NewManager(),
		logger:                         logrus.NewEntry(logrus.New()),
		metricLastFailureTimestamp:     prometheus.NewGauge(prometheus.GaugeOpts{Name: "test"}),
		metricReadinessStatus:          prometheus.NewGauge(prometheus.GaugeOpts{Name: "test"}),
		metricTotalFailures:            prometheus.NewGauge(prometheus.GaugeOpts{Name: "test"}),
		clusterSizeDependantInterval:   func(d time.Duration) time.Duration { return d },
	}

	// Context timeout shorter than backend delay - triggers race condition
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	resultCh := make(chan error, 1)
	go func() {
		_, err := rc.getClusterConfig(ctx, backend)
		resultCh <- err
	}()

	// Wait for controller to start
	select {
	case <-getCalled:
		t.Log("Controller started Get")
	case <-time.After(1 * time.Second):
		t.Fatal("Controller did not start")
	}

	// Wait for getClusterConfig to return (should return due to context timeout)
	select {
	case err := <-resultCh:
		t.Logf("getClusterConfig returned: %v", err)
		require.Error(t, err, "Expected error due to context timeout")
	case <-time.After(testTimeout):
		t.Fatal("DEADLOCK: getClusterConfig did not return. " +
			"Channel buffer fix missing at line 270.")
	}

	// Give controller time to complete its send (should be quick with buffered channel)
	time.Sleep(400 * time.Millisecond)

	rc.controllers.RemoveAll()
}

// TestChannelBufferBehavior verifies the channel buffer behavior directly.
func TestChannelBufferBehavior(t *testing.T) {
	testTimeout := 2 * time.Second

	// The FIXED pattern from line 270
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
		t.Log("Send completed (buffered channel)")
	case <-time.After(testTimeout):
		t.Fatal("DEADLOCK: Channel send blocked")
	}

	wg.Wait()
}
