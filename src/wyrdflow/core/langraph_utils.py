"""LangGraph enhancement utilities that work alongside pure LangGraph.

This module provides utilities that enhance LangGraph workflows with Wyrdflow
features while maintaining compatibility with pure LangGraph. The focus is on
enhancing the existing as_langraph_node() pattern with additional capabilities
like validation, automatic schema inference, and workflow analysis.

These utilities work with the existing simple_pipeline.py pattern where:
1. BaseNode.as_langraph_node() converts nodes to LangGraph-compatible functions
2. WorkflowState is serialized into LangGraph state as the single source of truth
3. Pure LangGraph StateGraph is used for workflow orchestration
"""

import logging
from typing import Any, Optional

from pydantic import ValidationError

from .base import BaseNode
from .config import NodeConfig
from .state import WorkflowState

logger = logging.getLogger(__name__)


class SchemaInference:
    """Utilities for automatic schema inference between connected nodes.

    This class provides methods to analyze node connections and ensure
    type compatibility, helping developers catch schema mismatches early.
    """

    @staticmethod
    def can_connect(
        from_node: BaseNode[Any, Any], to_node: BaseNode[Any, Any]
    ) -> tuple[bool, list[str]]:
        """Check if two nodes can be connected based on their schemas.

        Args:
            from_node: Source node
            to_node: Target node

        Returns:
            Tuple of (can_connect, list_of_issues)
        """
        issues = []

        # Get schemas
        from_output = getattr(from_node, "output_schema", None)
        to_input = getattr(to_node, "input_schema", None)

        if not from_output:
            issues.append(f"Source node '{from_node.node_id}' has no output schema")

        if not to_input:
            issues.append(f"Target node '{to_node.node_id}' has no input schema")

        if not from_output or not to_input:
            return False, issues

        # Check field compatibility
        from_fields = from_output.model_fields
        to_fields = to_input.model_fields

        # Find missing required fields
        missing_fields = []
        for field_name, field_info in to_fields.items():
            if field_info.is_required() and field_name not in from_fields:
                missing_fields.append(field_name)

        if missing_fields:
            issues.append(f"Missing required fields: {missing_fields}")

        # Check type compatibility for overlapping fields
        type_mismatches = []
        for field_name in set(from_fields.keys()) & set(to_fields.keys()):
            from_type = from_fields[field_name].annotation
            to_type = to_fields[field_name].annotation

            # Basic type compatibility check
            if from_type != to_type:
                type_mismatches.append(f"{field_name}: {from_type} -> {to_type}")

        if type_mismatches:
            issues.append(f"Type mismatches: {type_mismatches}")

        return len(issues) == 0, issues

    @staticmethod
    def analyze_graph_compatibility(
        nodes: dict[str, BaseNode[Any, Any]], edges: list[tuple[str, str]]
    ) -> dict[str, Any]:
        """Analyze schema compatibility across an entire graph.

        Args:
            nodes: Dictionary mapping node IDs to BaseNode instances
            edges: List of (from_node_id, to_node_id) tuples

        Returns:
            Analysis results with compatibility information
        """
        results: dict[str, Any] = {
            "compatible": True,
            "issues": [],
            "edge_analysis": {},
        }

        for from_id, to_id in edges:
            if from_id not in nodes or to_id not in nodes:
                results["issues"].append(f"Unknown nodes in edge: {from_id} -> {to_id}")
                results["compatible"] = False
                continue

            from_node = nodes[from_id]
            to_node = nodes[to_id]

            can_connect, issues = SchemaInference.can_connect(from_node, to_node)

            results["edge_analysis"][f"{from_id} -> {to_id}"] = {
                "compatible": can_connect,
                "issues": issues,
            }

            if not can_connect:
                results["compatible"] = False
                results["issues"].extend(
                    [f"Edge {from_id} -> {to_id}: {issue}" for issue in issues]
                )

        return results


class RuntimeValidator:
    """Runtime validation utilities for LangGraph state dictionaries.

    This class provides methods to validate data flowing through LangGraph
    workflows, ensuring type safety and catching data issues early.
    """

    @staticmethod
    def validate_node_input(
        node: BaseNode[Any, Any], state_data: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Validate that state data is compatible with a node's input schema.

        Args:
            node: The node to validate input for
            state_data: Current LangGraph state data

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        if not hasattr(node, "input_schema"):
            return True, []

        try:
            # Extract relevant input data from state
            # This mirrors the logic in as_langraph_node()
            if "input" in state_data and "last_node" not in state_data:
                # First node - use explicit input
                node_input = state_data["input"]
            else:
                # Subsequent nodes - use the entire state as input
                node_input = state_data.copy()
                # Remove internal LangGraph metadata
                internal_keys = {"workflow_state", "context", "last_node", "input"}
                for key in internal_keys:
                    node_input.pop(key, None)

            # Validate against schema
            node.validate_input(node_input)
            return True, []

        except ValidationError as e:
            error_messages = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            return False, error_messages
        except Exception as e:
            return False, [f"Validation error: {e!s}"]

    @staticmethod
    def validate_workflow_state(state_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate the WorkflowState within LangGraph state.

        Args:
            state_data: Current LangGraph state data

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        workflow_state_data = state_data.get("workflow_state", {})

        if not workflow_state_data:
            return True, []  # No workflow state to validate

        try:
            WorkflowState(**workflow_state_data)
            return True, []
        except ValidationError as e:
            error_messages = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            return False, error_messages
        except Exception as e:
            return False, [f"WorkflowState validation error: {e!s}"]


class WorkflowAnalyzer:
    """Analyzer for Wyrdflow-enhanced LangGraph workflows.

    This class provides methods to analyze workflow structure, detect
    potential issues, and provide insights for optimization.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, BaseNode[Any, Any]] = {}
        self.edges: list[tuple[str, str]] = []

    def add_node(self, node_id: str, node: BaseNode[Any, Any]) -> None:
        """Add a node to the analysis.

        Args:
            node_id: Node identifier
            node: BaseNode instance
        """
        self.nodes[node_id] = node

    def add_edge(self, from_node: str, to_node: str) -> None:
        """Add an edge to the analysis.

        Args:
            from_node: Source node ID
            to_node: Target node ID
        """
        self.edges.append((from_node, to_node))

    def analyze(self) -> dict[str, Any]:
        """Perform comprehensive workflow analysis.

        Returns:
            Analysis results with recommendations
        """
        results: dict[str, Any] = {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "schema_compatibility": SchemaInference.analyze_graph_compatibility(
                self.nodes, self.edges
            ),
            "node_types": self._analyze_node_types(),
            "potential_bottlenecks": self._identify_bottlenecks(),
            "recommendations": [],
        }

        # Generate recommendations
        if not results["schema_compatibility"]["compatible"]:
            results["recommendations"].append(
                "Fix schema compatibility issues before deployment"
            )

        if len(results["potential_bottlenecks"]) > 0:
            results["recommendations"].append(
                "Consider optimizing identified bottleneck nodes"
            )

        return results

    def _analyze_node_types(self) -> dict[str, Any]:
        """Analyze the types of nodes in the workflow."""
        type_counts: dict[str, int] = {}
        config_analysis: dict[str, Any] = {
            "pinned_outputs": 0,
            "high_retry_counts": [],
            "long_timeouts": [],
        }

        for node_id, node in self.nodes.items():
            node_type = node.__class__.__name__
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

            # Analyze configuration
            if node.config.is_output_pinned():
                config_analysis["pinned_outputs"] += 1

            if node.config.retry_attempts > 5:
                config_analysis["high_retry_counts"].append(node_id)

            if node.config.timeout > 300:
                config_analysis["long_timeouts"].append(node_id)

        return {
            "type_distribution": type_counts,
            "configuration_analysis": config_analysis,
        }

    def _identify_bottlenecks(self) -> list[str]:
        """Identify potential bottleneck nodes."""
        bottlenecks = []

        # Nodes with high timeout values might be bottlenecks
        for node_id, node in self.nodes.items():
            if node.config.timeout > 120:  # More than 2 minutes
                bottlenecks.append(f"{node_id}: High timeout ({node.config.timeout}s)")

        return bottlenecks


def create_enhanced_node(
    node_class: type[BaseNode[Any, Any]],
    node_id: str,
    config_overrides: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> BaseNode[Any, Any]:
    """Create a node with enhanced configuration options.

    This utility function makes it easier to create nodes with
    specific configuration overrides for testing or optimization.

    Args:
        node_class: BaseNode subclass to instantiate
        node_id: Unique node identifier
        config_overrides: Configuration values to override
        **kwargs: Additional arguments for node constructor

    Returns:
        Configured BaseNode instance
    """
    # Create base config
    config = kwargs.pop("config", NodeConfig())

    # Apply overrides
    if config_overrides:
        for key, value in config_overrides.items():
            setattr(config, key, value)

    return node_class(node_id=node_id, config=config, **kwargs)


def pin_node_output(node: BaseNode[Any, Any], output_data: Any) -> None:
    """Pin a node's output for testing purposes.

    This is a convenience function that makes it easy to pin outputs
    for testing scenarios where you want to skip expensive operations.

    Args:
        node: BaseNode instance to pin output for
        output_data: Data to return instead of executing the node
    """
    node.config.pin_output(output_data)
    logger.info(f"Pinned output for node '{node.node_id}' for testing")


def unpin_node_output(node: BaseNode[Any, Any]) -> None:
    """Remove output pinning from a node.

    Args:
        node: BaseNode instance to unpin output for
    """
    node.config.unpin_output()
    logger.info(f"Unpinned output for node '{node.node_id}'")


def validate_langraph_state(state_data: dict[str, Any]) -> dict[str, Any]:
    """Validate a LangGraph state dictionary for Wyrdflow compatibility.

    Args:
        state_data: LangGraph state dictionary

    Returns:
        Validation results with any issues found
    """
    is_valid, errors = RuntimeValidator.validate_workflow_state(state_data)

    return {
        "valid": is_valid,
        "errors": errors,
        "workflow_state_present": "workflow_state" in state_data,
        "context_present": "context" in state_data,
    }
