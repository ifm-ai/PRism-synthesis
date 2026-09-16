// Copyright 2023 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Hidden verifier test for TestGrpcCredentialsProvider_TokenType
// This test file defines its own tokenProvider to avoid conflicts with
// the package-level staticTP type which differs between buggy and fixed versions.
package grpctransport

import (
	"context"
	"log"
	"testing"

	"cloud.google.com/go/auth"
)

// testTokenProvider is a local token provider for this test.
// It shadows any package-level staticTP to ensure compatibility.
type testTokenProvider struct {
	tok *auth.Token
}

func (tp *testTokenProvider) Token(context.Context) (*auth.Token, error) {
	return tp.tok, nil
}

// TestGrpcCredentialsProvider_TokenType verifies that:
// 1. A token with explicit Type "Basic" produces "Basic <value>" in authorization header
// 2. A token with empty Type defaults to "Bearer <value>" in authorization header
//
// This test targets the fix that adds setAuthMetadata helper function which
// defaults empty token.Type to "Bearer" when constructing the authorization header.
func TestGrpcCredentialsProvider_TokenType(t *testing.T) {
	tests := []struct {
		name string
		tok  *auth.Token
		want string
	}{
		{
			name: "type set to Basic",
			tok: &auth.Token{
				Value: "token",
				Type:  "Basic",
			},
			want: "Basic token",
		},
		{
			name: "type empty defaults to Bearer",
			tok: &auth.Token{
				Value: "token",
				Type:  "",
			},
			want: "Bearer token",
		},
	}
	for _, tc := range tests {
		cp := &grpcCredentialsProvider{
			creds: &auth.Credentials{
				TokenProvider: &testTokenProvider{tok: tc.tok},
			},
		}
		m, err := cp.GetRequestMetadata(context.Background(), "")
		if err != nil {
			log.Fatalf("cp.GetRequestMetadata() = %v, want nil", err)
		}
		if got := m["authorization"]; got != tc.want {
			t.Fatalf("got %q, want %q", got, tc.want)
		}
	}
}
