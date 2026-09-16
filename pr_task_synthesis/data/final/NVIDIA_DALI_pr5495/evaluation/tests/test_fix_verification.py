# Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Test that verifies the fix.patch changes are correctly applied to DALI source code.

This test directly inspects the source files to verify that the API modernization
changes from std::string to std::string_view have been applied. This is a synthesis-time
verification that the fix was correctly applied.

Grounded in fix.patch, this test verifies:
1. InputFeedCount signature uses std::string_view in executor.h
2. GetOperator method is declared in ExecutorBase
3. NodePtr and NodeId methods exist in lowered_graph.h
4. TensorId returns std::optional in lowered_graph.h
5. input_operators_ uses std::less<> comparator in pipeline.h
"""

import os
import re
import pytest


# Path to the workspace source code
WORKSPACE_DIR = "/workspace"


def read_file(filepath):
    """Read a file and return its contents."""
    full_path = os.path.join(WORKSPACE_DIR, filepath)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Source file not found: {full_path}")
    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


class TestExecutorAPIChanges:
    """Test that executor API changes from fix.patch are applied."""

    def test_executor_h_has_string_view_inputfeedcount(self):
        """Verify InputFeedCount uses std::string_view in executor.h."""
        content = read_file("dali/pipeline/executor/executor.h")

        # The fix changes: DLL_PUBLIC virtual int InputFeedCount(const std::string &input_name) = 0;
        # To: DLL_PUBLIC virtual int InputFeedCount(std::string_view input_name) = 0;

        # Check for string_view version (fixed)
        has_string_view = re.search(r'InputFeedCount\s*\(\s*std::string_view\s+\w+\s*\)', content)

        # Check for old std::string version (buggy)
        has_old_string = re.search(r'InputFeedCount\s*\(\s*const\s+std::string\s*&\s*\w+\s*\)', content)

        assert has_string_view is not None, \
            "executor.h should have InputFeedCount(std::string_view) signature"
        assert has_old_string is None, \
            "executor.h should not have old InputFeedCount(const std::string&) signature"

    def test_executor_h_has_get_operator_method(self):
        """Verify GetOperator method is declared in ExecutorBase."""
        content = read_file("dali/pipeline/executor/executor.h")

        # The fix adds: DLL_PUBLIC virtual OperatorBase *GetOperator(std::string_view name) = 0;

        has_get_operator = re.search(r'GetOperator\s*\(\s*std::string_view\s+\w+\s*\)', content)

        assert has_get_operator is not None, \
            "executor.h should declare GetOperator(std::string_view) method"

    def test_executor_impl_has_get_operator_implementation(self):
        """Verify GetOperator is implemented in executor_impl.cc."""
        content = read_file("dali/pipeline/executor/executor_impl.cc")

        # The fix adds implementation for GetOperator
        has_implementation = (
            'OperatorBase *Executor<WorkspacePolicy, QueuePolicy>::GetOperator' in content or
            'OperatorBase* Executor<WorkspacePolicy, QueuePolicy>::GetOperator' in content
        )

        assert has_implementation, \
            "executor_impl.cc should implement GetOperator method"

    def test_executor_impl_inputfeedcount_uses_string_view(self):
        """Verify InputFeedCount implementation uses std::string_view."""
        content = read_file("dali/pipeline/executor/executor_impl.cc")

        has_string_view = re.search(
            r'InputFeedCount\s*\(\s*std::string_view\s+\w+\s*\)',
            content
        )

        assert has_string_view is not None, \
            "executor_impl.cc should have InputFeedCount(std::string_view) implementation"


class TestOpGraphAPIChanges:
    """Test that OpGraph API changes from fix.patch are applied."""

    def test_lowered_graph_has_nodeptr_method(self):
        """Verify NodePtr method exists in lowered_graph.h."""
        content = read_file("dali/pipeline/executor/lowered_graph.h")

        # The fix adds: DLL_PUBLIC OpNode *NodePtr(std::string_view instance_name);
        has_nodeptr = re.search(r'NodePtr\s*\(\s*std::string_view\s+\w+\s*\)', content)

        assert has_nodeptr is not None, \
            "lowered_graph.h should declare NodePtr(std::string_view) method"

    def test_lowered_graph_has_nodeid_method(self):
        """Verify NodeId method exists in lowered_graph.h."""
        content = read_file("dali/pipeline/executor/lowered_graph.h")

        # The fix adds: DLL_PUBLIC std::optional<OpNodeId> NodeId(std::string_view instance_name);
        has_nodeid = re.search(r'NodeId\s*\(\s*std::string_view\s+\w+\s*\)', content)

        assert has_nodeid is not None, \
            "lowered_graph.h should declare NodeId(std::string_view) method"

    def test_lowered_graph_tensorid_returns_optional(self):
        """Verify TensorId returns std::optional."""
        content = read_file("dali/pipeline/executor/lowered_graph.h")

        # The fix changes TensorId to return std::optional<TensorNodeId>
        has_optional = re.search(r'std::optional<TensorNodeId>\s+TensorId', content)

        assert has_optional is not None, \
            "lowered_graph.h should have TensorId returning std::optional<TensorNodeId>"

    def test_lowered_graph_has_tensorptr_method(self):
        """Verify TensorPtr method exists in lowered_graph.h."""
        content = read_file("dali/pipeline/executor/lowered_graph.h")

        # The fix adds: DLL_PUBLIC const TensorNode *TensorPtr(std::string_view name) const;
        has_tensorptr = re.search(r'TensorPtr\s*\(\s*std::string_view\s+\w+\s*\)', content)

        assert has_tensorptr is not None, \
            "lowered_graph.h should declare TensorPtr(std::string_view) method"

    def test_lowered_graph_uses_less_comparator(self):
        """Verify maps use std::less<> for heterogeneous lookup."""
        content = read_file("dali/pipeline/executor/lowered_graph.h")

        # The fix changes:
        # std::map<std::string, TensorNodeId> tensor_name_to_id_;
        # To: std::map<std::string, TensorNodeId, std::less<>> tensor_name_to_id_;

        has_heterogeneous_map = re.search(
            r'std::map<std::string,\s*\w+,\s*std::less<>\s*>',
            content
        )

        assert has_heterogeneous_map is not None, \
            "lowered_graph.h should use std::less<> for heterogeneous map lookup"

    def test_lowered_graph_addop_returns_reference(self):
        """Verify AddOp returns OpNode& instead of void."""
        content = read_file("dali/pipeline/executor/lowered_graph.h")

        # The fix changes: void AddOp(...) to OpNode &AddOp(...)
        has_return_ref = re.search(r'OpNode\s*&\s*AddOp\s*\(', content)

        assert has_return_ref is not None, \
            "lowered_graph.h should have AddOp returning OpNode&"


class TestPipelineAPIChanges:
    """Test that Pipeline API changes from fix.patch are applied."""

    def test_pipeline_h_inputfeedcount_uses_string_view(self):
        """Verify Pipeline::InputFeedCount uses std::string_view."""
        content = read_file("dali/pipeline/pipeline.h")

        has_string_view = re.search(
            r'InputFeedCount\s*\(\s*std::string_view\s+\w+\s*\)',
            content
        )

        assert has_string_view is not None, \
            "pipeline.h should have InputFeedCount(std::string_view)"

    def test_pipeline_h_getoperatornode_uses_string_view(self):
        """Verify Pipeline::GetOperatorNode uses std::string_view."""
        content = read_file("dali/pipeline/pipeline.h")

        has_string_view = re.search(
            r'GetOperatorNode\s*\(\s*std::string_view\s+\w+\s*\)',
            content
        )

        assert has_string_view is not None, \
            "pipeline.h should have GetOperatorNode(std::string_view)"

    def test_pipeline_h_getinputoperatornode_uses_string_view(self):
        """Verify Pipeline::GetInputOperatorNode uses std::string_view."""
        content = read_file("dali/pipeline/pipeline.h")

        has_string_view = re.search(
            r'GetInputOperatorNode\s*\(\s*std::string_view\s+\w+\s*\)',
            content
        )

        assert has_string_view is not None, \
            "pipeline.h should have GetInputOperatorNode(std::string_view)"

    def test_pipeline_h_getreadermeta_uses_string_view(self):
        """Verify Pipeline::GetReaderMeta uses std::string_view."""
        content = read_file("dali/pipeline/pipeline.h")

        has_string_view = re.search(
            r'GetReaderMeta\s*\(\s*std::string_view\s+\w+\s*\)',
            content
        )

        assert has_string_view is not None, \
            "pipeline.h should have GetReaderMeta(std::string_view)"

    def test_pipeline_h_getinputlayout_uses_string_view(self):
        """Verify Pipeline::GetInputLayout uses std::string_view."""
        content = read_file("dali/pipeline/pipeline.h")

        has_string_view = re.search(
            r'GetInputLayout\s*\(\s*std::string_view\s+\w+\s*\)',
            content
        )

        assert has_string_view is not None, \
            "pipeline.h should have GetInputLayout(std::string_view)"

    def test_pipeline_h_getinputndim_uses_string_view(self):
        """Verify Pipeline::GetInputNdim uses std::string_view."""
        content = read_file("dali/pipeline/pipeline.h")

        has_string_view = re.search(
            r'GetInputNdim\s*\(\s*std::string_view\s+\w+\s*\)',
            content
        )

        assert has_string_view is not None, \
            "pipeline.h should have GetInputNdim(std::string_view)"

    def test_pipeline_h_getinputdtype_uses_string_view(self):
        """Verify Pipeline::GetInputDtype uses std::string_view."""
        content = read_file("dali/pipeline/pipeline.h")

        has_string_view = re.search(
            r'GetInputDtype\s*\(\s*std::string_view\s+\w+\s*\)',
            content
        )

        assert has_string_view is not None, \
            "pipeline.h should have GetInputDtype(std::string_view)"

    def test_pipeline_h_input_operators_uses_less_comparator(self):
        """Verify input_operators_ map uses std::less<> for heterogeneous lookup."""
        content = read_file("dali/pipeline/pipeline.h")

        # The fix changes:
        # std::map<std::string, const OpNode*> input_operators_;
        # To: std::map<std::string, const OpNode*, std::less<>> input_operators_;

        has_heterogeneous_map = re.search(
            r'input_operators_.*std::less<>\s*>|std::less<>\s*>.*input_operators_',
            content
        )

        assert has_heterogeneous_map is not None, \
            "pipeline.h should use std::less<> for input_operators_ map"


class TestImplementationChanges:
    """Test that implementation files have the correct changes."""

    def test_pipeline_cc_getoperatornode_implementation(self):
        """Verify GetOperatorNode implementation uses std::string_view."""
        content = read_file("dali/pipeline/pipeline.cc")

        has_string_view = re.search(
            r'GetOperatorNode\s*\(\s*std::string_view\s+\w+\s*\)',
            content
        )

        assert has_string_view is not None, \
            "pipeline.cc should implement GetOperatorNode with std::string_view"

    def test_pipeline_cc_getreadermeta_uses_executor_getoperator(self):
        """Verify GetReaderMeta uses executor_->GetOperator()."""
        content = read_file("dali/pipeline/pipeline.cc")

        # The fix changes GetReaderMeta to use executor_->GetOperator(name)
        # instead of iterating through graph nodes
        has_executor_getop = 'executor_->GetOperator(name)' in content or \
                            'executor_->GetOperator(name)' in content.replace(' ', '')

        assert has_executor_getop, \
            "pipeline.cc GetReaderMeta should use executor_->GetOperator()"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
