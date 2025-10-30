"""Tests for registry module."""

import pytest

from wyrdflow.core import (
    BaseNode,
    NodeContext,
    NodeInput,
    NodeOutput,
    NodeSpecificConfig,
    WorkflowState,
)
from wyrdflow.core.registry import (
    NodeRegistry,
    NodeTypeInfo,
    get_registry,
    register_node,
)


# Test schemas
class ExampleRegistryInput(NodeInput):
    value: int


class ExampleRegistryOutput(NodeOutput):
    result: str


# Test node specific config
class ExampleNodeConfig(NodeSpecificConfig):
    test_param: str = "default"
    test_count: int = 1


# Test nodes
class ExampleRegistryNode(BaseNode):
    input_schema = ExampleRegistryInput
    output_schema = ExampleRegistryOutput
    config_schema = ExampleNodeConfig

    async def execute(
        self,
        input_data: ExampleRegistryInput,
        context: NodeContext,
        state: WorkflowState,
    ) -> ExampleRegistryOutput:
        return ExampleRegistryOutput(result=f"processed_{input_data.value}")


class AnotherTestNode(BaseNode):
    input_schema = ExampleRegistryInput
    output_schema = ExampleRegistryOutput

    async def execute(
        self,
        input_data: ExampleRegistryInput,
        context: NodeContext,
        state: WorkflowState,
    ) -> ExampleRegistryOutput:
        return ExampleRegistryOutput(result=f"another_{input_data.value}")


class TestNodeTypeInfo:
    """Test NodeTypeInfo class."""

    def test_node_type_info_creation(self):
        """Test basic NodeTypeInfo creation."""
        info = NodeTypeInfo(
            ExampleRegistryNode,
            "TestNode",
            description="A test node",
            category="testing",
            tags=["test", "example"],
        )

        assert info.node_class == ExampleRegistryNode
        assert info.name == "TestNode"
        assert info.description == "A test node"
        assert info.category == "testing"
        assert info.tags == ["test", "example"]
        assert info.config_schema == ExampleNodeConfig

    def test_node_type_info_minimal(self):
        """Test NodeTypeInfo with minimal parameters."""
        info = NodeTypeInfo(ExampleRegistryNode, "TestNode")

        assert info.node_class == ExampleRegistryNode
        assert info.name == "TestNode"
        # When no description provided, it generates a default
        assert info.description == "Node type: TestNode"
        # When no category provided, it defaults to "General"
        assert info.category == "General"
        assert info.tags == []

    def test_extract_config_schema(self):
        """Test config schema extraction."""
        info = NodeTypeInfo(ExampleRegistryNode, "TestNode")
        assert info.config_schema == ExampleNodeConfig

        # Test node without config schema
        info_no_config = NodeTypeInfo(AnotherTestNode, "AnotherNode")
        assert info_no_config.config_schema is None

    def test_to_dict(self):
        """Test dictionary serialization."""
        info = NodeTypeInfo(
            ExampleRegistryNode,
            "TestNode",
            description="A test node",
            category="testing",
            tags=["test", "example"],
        )

        data = info.to_dict()

        assert data["name"] == "TestNode"
        assert data["description"] == "A test node"
        assert data["category"] == "testing"
        assert data["tags"] == ["test", "example"]
        assert data["class_name"] == "ExampleRegistryNode"
        assert data["module"] == "test_registry"  # Actual module name when run
        assert "input_schema" in data
        assert "output_schema" in data
        assert "config_schema" in data


class TestNodeRegistry:
    """Test NodeRegistry class."""

    def setup_method(self):
        """Set up test registry."""
        self.registry = NodeRegistry()

    def test_registry_initialization(self):
        """Test registry initialization."""
        assert len(self.registry._nodes) == 0
        assert len(self.registry._categories) == 0
        assert len(self.registry._tags) == 0

    def test_register_node_basic(self):
        """Test basic node registration."""
        self.registry.register(ExampleRegistryNode, "TestNode")

        assert "TestNode" in self.registry._nodes
        node_info = self.registry._nodes["TestNode"]
        assert node_info.node_class == ExampleRegistryNode
        assert node_info.name == "TestNode"

    def test_register_node_full(self):
        """Test node registration with all parameters."""
        self.registry.register(
            ExampleRegistryNode,
            "TestNode",
            description="A test node",
            category="testing",
            tags=["test", "example"],
        )

        node_info = self.registry._nodes["TestNode"]
        assert node_info.description == "A test node"
        assert node_info.category == "testing"
        assert node_info.tags == ["test", "example"]

        # Check category and tag tracking
        assert "testing" in self.registry._categories
        assert "TestNode" in self.registry._categories["testing"]
        assert "test" in self.registry._tags
        assert "example" in self.registry._tags

    def test_register_node_auto_name(self):
        """Test node registration with automatic name."""
        self.registry.register(ExampleRegistryNode)

        # Should use class name
        assert "ExampleRegistryNode" in self.registry._nodes

    def test_register_duplicate_node(self):
        """Test registering duplicate node name."""
        self.registry.register(ExampleRegistryNode, "TestNode")

        # Should raise error without override
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(AnotherTestNode, "TestNode")

    def test_register_duplicate_node_with_override(self):
        """Test registering duplicate node with override."""
        self.registry.register(ExampleRegistryNode, "TestNode")
        self.registry.register(AnotherTestNode, "TestNode", override=True)

        # Should be replaced
        node_info = self.registry._nodes["TestNode"]
        assert node_info.node_class == AnotherTestNode

    def test_unregister_node(self):
        """Test node unregistration."""
        self.registry.register(
            ExampleRegistryNode,
            "TestNode",
            category="testing",
            tags=["test"],
        )

        result = self.registry.unregister("TestNode")
        assert result is True
        assert "TestNode" not in self.registry._nodes

        # Category and tags should be cleaned up
        assert (
            "testing" not in self.registry._categories
            or len(self.registry._categories["testing"]) == 0
        )
        assert (
            "test" not in self.registry._tags or len(self.registry._tags["test"]) == 0
        )

    def test_unregister_nonexistent_node(self):
        """Test unregistering non-existent node."""
        result = self.registry.unregister("NonExistent")
        assert result is False

    def test_get_node_info(self):
        """Test getting node info."""
        self.registry.register(ExampleRegistryNode, "TestNode")

        info = self.registry.get_node_info("TestNode")
        assert info is not None
        assert info.node_class == ExampleRegistryNode

        # Non-existent node
        info = self.registry.get_node_info("NonExistent")
        assert info is None

    def test_get_node_class(self):
        """Test getting node class."""
        self.registry.register(ExampleRegistryNode, "TestNode")

        node_class = self.registry.get_node_class("TestNode")
        assert node_class == ExampleRegistryNode

        # Non-existent node
        node_class = self.registry.get_node_class("NonExistent")
        assert node_class is None

    def test_list_nodes_all(self):
        """Test listing all nodes."""
        self.registry.register(ExampleRegistryNode, "TestNode1", category="cat1")
        self.registry.register(AnotherTestNode, "TestNode2", category="cat2")

        nodes = self.registry.list_nodes()
        assert len(nodes) == 2
        names = [node.name for node in nodes]
        assert "TestNode1" in names
        assert "TestNode2" in names

    def test_list_nodes_by_category(self):
        """Test listing nodes by category."""
        self.registry.register(ExampleRegistryNode, "TestNode1", category="cat1")
        self.registry.register(AnotherTestNode, "TestNode2", category="cat2")

        nodes = self.registry.list_nodes(category="cat1")
        assert len(nodes) == 1
        assert nodes[0].name == "TestNode1"

    def test_list_nodes_by_tag(self):
        """Test listing nodes by tag."""
        self.registry.register(ExampleRegistryNode, "TestNode1", tags=["tag1", "tag2"])
        self.registry.register(AnotherTestNode, "TestNode2", tags=["tag2", "tag3"])

        nodes = self.registry.list_nodes(tag="tag2")
        assert len(nodes) == 2

        nodes = self.registry.list_nodes(tag="tag1")
        assert len(nodes) == 1
        assert nodes[0].name == "TestNode1"

    def test_list_categories(self):
        """Test listing categories."""
        self.registry.register(ExampleRegistryNode, "TestNode1", category="cat1")
        self.registry.register(AnotherTestNode, "TestNode2", category="cat2")

        categories = self.registry.list_categories()
        assert len(categories) == 2
        assert "cat1" in categories
        assert "cat2" in categories

    def test_list_tags(self):
        """Test listing tags."""
        self.registry.register(ExampleRegistryNode, "TestNode1", tags=["tag1", "tag2"])
        self.registry.register(AnotherTestNode, "TestNode2", tags=["tag2", "tag3"])

        tags = self.registry.list_tags()
        assert len(tags) == 3
        assert "tag1" in tags
        assert "tag2" in tags
        assert "tag3" in tags

    def test_find_nodes_by_name_pattern(self):
        """Test finding nodes by name pattern."""
        self.registry.register(ExampleRegistryNode, "TestNode1")
        self.registry.register(AnotherTestNode, "AnotherNode1")

        nodes = self.registry.find_nodes(name_pattern="Test")  # Use substring match
        assert len(nodes) == 1
        assert nodes[0].name == "TestNode1"

    def test_find_nodes_by_description_pattern(self):
        """Test finding nodes by description pattern."""
        self.registry.register(
            ExampleRegistryNode,
            "TestNode1",
            description="This is a test node",
        )
        self.registry.register(
            AnotherTestNode,
            "AnotherNode1",
            description="This is another node",
        )

        nodes = self.registry.find_nodes(description_pattern="test")
        assert len(nodes) == 1
        assert nodes[0].name == "TestNode1"

    def test_find_nodes_multiple_criteria(self):
        """Test finding nodes with multiple criteria."""
        self.registry.register(
            ExampleRegistryNode,
            "TestNode1",
            category="testing",
            tags=["test"],
        )
        self.registry.register(
            AnotherTestNode,
            "TestNode2",
            category="testing",
            tags=["example"],
        )

        nodes = self.registry.find_nodes(category="testing", tag="test")
        assert len(nodes) == 1
        assert nodes[0].name == "TestNode1"

    def test_to_dict(self):
        """Test registry serialization."""
        self.registry.register(ExampleRegistryNode, "TestNode1", category="cat1")
        self.registry.register(AnotherTestNode, "TestNode2", category="cat2")

        data = self.registry.to_dict()

        assert "nodes" in data
        assert "categories" in data
        assert "tags" in data
        assert len(data["nodes"]) == 2
        assert "cat1" in data["categories"]
        assert "cat2" in data["categories"]

    def test_node_count(self):
        """Test node count."""
        assert len(self.registry._nodes) == 0

        self.registry.register(ExampleRegistryNode, "TestNode1")
        assert len(self.registry._nodes) == 1

        self.registry.register(AnotherTestNode, "TestNode2")
        assert len(self.registry._nodes) == 2

        self.registry.unregister("TestNode1")
        assert len(self.registry._nodes) == 1


class TestGlobalRegistry:
    """Test global registry functions."""

    def test_get_registry_singleton(self):
        """Test that get_registry returns singleton."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_register_node_function(self):
        """Test register_node convenience function."""
        # Clear any existing registrations
        registry = get_registry()
        if "ExampleRegistryNode" in registry._nodes:
            registry.unregister("ExampleRegistryNode")

        register_node(
            ExampleRegistryNode,
            "ExampleRegistryNode",
            description="A test node",
            category="testing",
            tags=["test"],
        )

        registry = get_registry()
        assert "ExampleRegistryNode" in registry._nodes
        node_info = registry.get_node_info("ExampleRegistryNode")
        assert node_info is not None
        assert node_info.description == "A test node"
        assert node_info.category == "testing"
        assert node_info.tags == ["test"]

    def test_register_node_function_minimal(self):
        """Test register_node with minimal parameters."""
        register_node(AnotherTestNode)

        registry = get_registry()
        assert "AnotherTestNode" in registry._nodes


class TestErrorHandling:
    """Test error handling in registry."""

    def test_invalid_node_class(self):
        """Test registering invalid node class."""
        registry = NodeRegistry()

        with pytest.raises(ValueError):  # Registry raises ValueError, not TypeError
            registry.register(str, "InvalidNode")  # type: ignore

    def test_empty_name(self):
        """Test registering with empty name falls back to class name."""
        registry = NodeRegistry()

        # Empty name should fall back to class name
        registry.register(ExampleRegistryNode, "")
        nodes = registry.list_nodes()
        assert len(nodes) == 1
        assert nodes[0].name == "ExampleRegistryNode"  # Uses class name

    def test_none_name(self):
        """Test registering with None name when class has no __name__."""
        registry = NodeRegistry()

        # This should work - uses class name
        registry.register(ExampleRegistryNode, None)
        assert "ExampleRegistryNode" in registry._nodes


class TestRegistryCleanup:
    """Test registry cleanup operations."""

    def test_category_cleanup_on_unregister(self):
        """Test that categories are cleaned up when last node is removed."""
        registry = NodeRegistry()

        registry.register(ExampleRegistryNode, "TestNode1", category="unique_cat")
        assert "unique_cat" in registry._categories

        registry.unregister("TestNode1")
        assert (
            "unique_cat" not in registry._categories
            or len(registry._categories["unique_cat"]) == 0
        )

    def test_tag_cleanup_on_unregister(self):
        """Test that tags are cleaned up when last node is removed."""
        registry = NodeRegistry()

        registry.register(ExampleRegistryNode, "TestNode1", tags=["unique_tag"])
        assert "unique_tag" in registry._tags

        registry.unregister("TestNode1")
        assert (
            "unique_tag" not in registry._tags or len(registry._tags["unique_tag"]) == 0
        )

    def test_partial_cleanup(self):
        """Test that shared categories/tags are not removed."""
        registry = NodeRegistry()

        registry.register(
            ExampleRegistryNode, "TestNode1", category="shared", tags=["shared"]
        )
        registry.register(
            AnotherTestNode, "TestNode2", category="shared", tags=["shared"]
        )

        registry.unregister("TestNode1")

        # Should still exist because TestNode2 uses them
        assert "shared" in registry._categories
        assert "shared" in registry._tags
        assert len(registry._categories["shared"]) == 1
        assert len(registry._tags["shared"]) == 1
