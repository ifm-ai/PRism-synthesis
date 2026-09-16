package test

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

// parseIAMPolicyFile extracts the actions array from the member-access policy document
// by parsing the Terraform file and extracting the JSON policy
func parseIAMPolicyActions(t *testing.T, iamFilePath string) []string {
	content, err := os.ReadFile(iamFilePath)
	assert.NoError(t, err, "Failed to read IAM policy file")

	// Extract the actions array from the Terraform file
	// The actions are in the format: "service:action", within the member-access policy document
	contentStr := string(content)

	// Find the member-access policy document block
	// Look for the actions array within data "aws_iam_policy_document" "member-access"
	startIdx := strings.Index(contentStr, `data "aws_iam_policy_document" "member-access"`)
	assert.NotEqual(t, -1, startIdx, "Could not find member-access policy document")

	// Extract the actions section - look for actions = [ ... ]
	actionsStart := strings.Index(contentStr[startIdx:], "actions = [")
	assert.NotEqual(t, -1, actionsStart, "Could not find actions array")
	actionsStart += startIdx + len("actions = [")

	// Find the closing bracket
	actionsEnd := strings.Index(contentStr[actionsStart:], "]")
	assert.NotEqual(t, -1, actionsEnd, "Could not find end of actions array")
	actionsEnd += actionsStart

	actionsBlock := contentStr[actionsStart:actionsEnd]

	// Extract all quoted action strings
	re := regexp.MustCompile(`"([^"]+)"`)
	matches := re.FindAllStringSubmatch(actionsBlock, -1)

	var actions []string
	for _, match := range matches {
		actions = append(actions, match[1])
	}

	return actions
}

// containsAction checks if an exact action string exists in the actions list
func containsAction(actions []string, action string) bool {
	for _, a := range actions {
		if a == action {
			return true
		}
	}
	return false
}

// containsActionPattern checks if any action matches the given pattern
func containsActionPattern(actions []string, pattern string) bool {
	re := regexp.MustCompile("^" + pattern + "$")
	for _, a := range actions {
		if re.MatchString(a) {
			return true
		}
	}
	return false
}

// TestIAMPolicy_NoOverlyBroadCognitoWildcard verifies that the overly broad cognito:* wildcard is removed
// This is a key security fix - cognito:* grants excessive permissions
func TestIAMPolicy_NoOverlyBroadCognitoWildcard(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")
	actions := parseIAMPolicyActions(t, iamPath)

	// The fix removes "cognito:*" - this overly broad wildcard should NOT be present
	assert.False(t, containsAction(actions, "cognito:*"),
		"Policy should NOT contain overly broad 'cognito:*' wildcard - this is a security risk")
}

// TestIAMPolicy_CognitoIdpSpecificPermission verifies that cognito-idp:* is still present
// The specific cognito-idp permission is needed and should remain
func TestIAMPolicy_CognitoIdpSpecificPermission(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")
	actions := parseIAMPolicyActions(t, iamPath)

	// cognito-idp:* should still be present - this is the specific permission needed
	assert.True(t, containsAction(actions, "cognito-idp:*"),
		"Policy should contain 'cognito-idp:*' - this specific permission is required")
}

// TestIAMPolicy_EC2DescribeConsolidated verifies that EC2 describe actions are consolidated under ec2:Describe*
// The fix consolidates individual describe actions under the ec2:Describe* wildcard
func TestIAMPolicy_EC2DescribeConsolidated(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")
	actions := parseIAMPolicyActions(t, iamPath)

	// The fix adds ec2:Describe* to cover all describe actions
	assert.True(t, containsAction(actions, "ec2:Describe*"),
		"Policy should contain 'ec2:Describe*' - consolidated describe permissions")
}

// TestIAMPolicy_EC2ModifyVpcWildcard verifies that VPC modification actions use ec2:ModifyVpc* wildcard
// The fix replaces specific VPC modification actions with ec2:ModifyVpc*
func TestIAMPolicy_EC2ModifyVpcWildcard(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")
	actions := parseIAMPolicyActions(t, iamPath)

	// The fix adds ec2:ModifyVpc* to cover all VPC modification operations
	assert.True(t, containsAction(actions, "ec2:ModifyVpc*"),
		"Policy should contain 'ec2:ModifyVpc*' - consolidated VPC modification permissions")
}

// TestIAMPolicy_RouteTablePermissions verifies that route table permissions are added
// The fix adds permissions for associating and managing route tables
func TestIAMPolicy_RouteTablePermissions(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")
	actions := parseIAMPolicyActions(t, iamPath)

	// New permissions for route tables
	assert.True(t, containsAction(actions, "ec2:AssociateRouteTable"),
		"Policy should contain 'ec2:AssociateRouteTable' - required for route table management")
	assert.True(t, containsAction(actions, "ec2:CreateRouteTable"),
		"Policy should contain 'ec2:CreateRouteTable' - required for route table management")
	assert.True(t, containsAction(actions, "ec2:DeleteRouteTable"),
		"Policy should contain 'ec2:DeleteRouteTable' - required for route table management")
}

// TestIAMPolicy_NetworkACLPermissions verifies that network ACL permissions are added
// The fix adds ec2:*NetworkAcl* to handle network ACLs
func TestIAMPolicy_NetworkACLPermissions(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")
	actions := parseIAMPolicyActions(t, iamPath)

	// New permissions for network ACLs
	assert.True(t, containsActionPattern(actions, "ec2:.*NetworkAcl.*"),
		"Policy should contain network ACL permissions (ec2:*NetworkAcl*) - required for VPC configuration")
}

// TestIAMPolicy_FlowLogsPermissions verifies that flow logs permissions are added
// The fix adds ec2:*FlowLogs to handle VPC flow logs
func TestIAMPolicy_FlowLogsPermissions(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")
	actions := parseIAMPolicyActions(t, iamPath)

	// New permissions for flow logs
	assert.True(t, containsActionPattern(actions, "ec2:.*FlowLogs"),
		"Policy should contain flow logs permissions (ec2:*FlowLogs) - required for VPC monitoring")
}

// TestIAMPolicy_NoDuplicateDescribeVpcEndpointActions verifies that specific describe actions
// that are covered by ec2:Describe* are not duplicated as individual entries
func TestIAMPolicy_NoDuplicateDescribeVpcEndpointActions(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")
	actions := parseIAMPolicyActions(t, iamPath)

	// These specific describe actions should NOT be present individually
	// because they are covered by ec2:Describe*
	// Note: The fix removes these in favor of the consolidated ec2:Describe*
	assert.False(t, containsAction(actions, "ec2:DescribeVpcEndpointServiceConfigurations"),
		"Policy should not have individual 'ec2:DescribeVpcEndpointServiceConfigurations' - covered by ec2:Describe*")
	assert.False(t, containsAction(actions, "ec2:DescribeVpcEndpointServicePermissions"),
		"Policy should not have individual 'ec2:DescribeVpcEndpointServicePermissions' - covered by ec2:Describe*")
}

// TestIAMPolicy_NoIndividualModifyVpcActions verifies that specific VPC modification actions
// are replaced by the ec2:ModifyVpc* wildcard
func TestIAMPolicy_NoIndividualModifyVpcActions(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")
	actions := parseIAMPolicyActions(t, iamPath)

	// These specific modify actions should NOT be present individually
	// because they are covered by ec2:ModifyVpc*
	assert.False(t, containsAction(actions, "ec2:ModifyVpcEndpointServiceConfiguration"),
		"Policy should not have individual 'ec2:ModifyVpcEndpointServiceConfiguration' - covered by ec2:ModifyVpc*")
	assert.False(t, containsAction(actions, "ec2:ModifyVpcEndpointServicePermissions"),
		"Policy should not have individual 'ec2:ModifyVpcEndpointServicePermissions' - covered by ec2:ModifyVpc*")
}

// TestIAMPolicy_StructureValid verifies that the policy file is valid Terraform
// and can be parsed correctly
func TestIAMPolicy_StructureValid(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")

	// Read the file and verify it's valid
	content, err := os.ReadFile(iamPath)
	assert.NoError(t, err, "Failed to read IAM policy file")
	assert.NotEmpty(t, content, "IAM policy file is empty")

	// Verify the file contains the expected Terraform structure
	contentStr := string(content)
	assert.Contains(t, contentStr, `data "aws_iam_policy_document" "member-access"`,
		"Policy file should contain member-access policy document")
	assert.Contains(t, contentStr, "actions = [",
		"Policy file should contain actions array")
}

// TestIAMPolicy_ExpectedActionCount verifies the policy has a reasonable number of actions
// This helps detect if actions were accidentally removed
func TestIAMPolicy_ExpectedActionCount(t *testing.T) {
	iamPath := filepath.Join("/workspace", "terraform", "environments", "bootstrap", "member-bootstrap", "iam.tf")
	actions := parseIAMPolicyActions(t, iamPath)

	// The policy should have a substantial number of actions (at least 50)
	// This ensures we didn't accidentally remove too many permissions
	assert.Greater(t, len(actions), 50,
		"Policy should have at least 50 actions - detected %d actions", len(actions))
}
