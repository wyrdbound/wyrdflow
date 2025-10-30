"""Node registry for discovering and managing node types."""

import inspect
import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .base import BaseNode
    from .config import NodeSpecificConfig
else:
    # For runtime, import without type parameters to avoid issues
    from .base import BaseNode
    from .config import NodeSpecificConfig

logger = logging.getLogger(__name__)


class NodeTypeInfo:
    """Information about a registered node type."""

    def __init__(
        self,
        node_class: "type[BaseNode[Any, Any]]",
        name: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ):
        self.node_class = node_class
        self.name = name
        self.description = description or node_class.__doc__ or f"Node type: {name}"
        self.category = category or "General"
        self.tags = tags or []

        # Extract schema information
        self.input_schema = getattr(node_class, "input_schema", None)
        self.output_schema = getattr(node_class, "output_schema", None)

        # Extract configuration information if available
        self.config_schema = self._extract_config_schema(node_class)

    def _extract_config_schema(
        self, node_class: "type[BaseNode[Any, Any]]"
    ) -> "Optional[type[NodeSpecificConfig]]":
        """Extract the configuration schema from the node class if it exists."""
        try:
            # First check for class attribute (explicit declaration)
            config_schema = getattr(node_class, "config_schema", None)
            if (
                config_schema
                and inspect.isclass(config_schema)
                and issubclass(config_schema, NodeSpecificConfig)
            ):
                return config_schema  # type: ignore[no-any-return]

            # Then look for config type hints in __init__ method
            init_signature = inspect.signature(node_class.__init__)
            if "config" in init_signature.parameters:
                param = init_signature.parameters["config"]
                if hasattr(param.annotation, "__origin__"):
                    # Handle generic types like TypedNodeConfig[SomeConfig]
                    args = getattr(param.annotation, "__args__", ())
                    if (
                        args
                        and inspect.isclass(args[0])
                        and issubclass(args[0], NodeSpecificConfig)
                    ):
                        return args[0]
                elif inspect.isclass(param.annotation) and issubclass(
                    param.annotation, NodeSpecificConfig
                ):
                    return param.annotation
        except Exception as e:
            logger.debug(
                f"Could not extract config schema for {node_class.__name__}: {e}"
            )
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert node type info to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "class_name": self.node_class.__name__,
            "module": self.node_class.__module__,
            "input_schema": self.input_schema.__name__ if self.input_schema else None,
            "output_schema": self.output_schema.__name__
            if self.output_schema
            else None,
            "config_schema": self.config_schema.__name__
            if self.config_schema
            else None,
        }


class NodeRegistry:
    """Registry for discovering and managing node types.

    This registry provides a central location for registering and discovering
    node types. It supports categorization, tagging, and metadata for each
    node type, which will be useful for future CLI and web interfaces.

    Example:
        ```python
        # Register a node type
        registry = NodeRegistry()
        registry.register(
            HTTPRequestNode,
            name="HTTP Request",
            description="Make HTTP requests to external APIs",
            category="Integration",
            tags=["http", "api", "external"]
        )

        # Discover nodes
        all_nodes = registry.list_nodes()
        http_nodes = registry.find_nodes(category="Integration")
        ```
    """

    def __init__(self) -> None:
        self._nodes: dict[str, NodeTypeInfo] = {}
        self._categories: dict[str, list[str]] = {}
        self._tags: dict[str, list[str]] = {}

    def register(
        self,
        node_class: "type[BaseNode[Any, Any]]",
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        override: bool = False,
    ) -> None:
        """Register a node type in the registry.

        Args:
            node_class: The node class to register
            name: Human-readable name for the node type (defaults to class name)
            description: Description of what the node does
            category: Category for organizing nodes (defaults to "General")
            tags: List of tags for searching and filtering
            override: Whether to override an existing registration

        Raises:
            ValueError: If node is already registered and override is False
        """
        node_name = name or node_class.__name__

        if node_name in self._nodes and not override:
            raise ValueError(
                f"Node type '{node_name}' is already registered. Use override=True to replace it."
            )

        # Validate that the class is actually a BaseNode
        if not (inspect.isclass(node_class) and issubclass(node_class, BaseNode)):
            raise ValueError(f"Node class {node_class} must be a subclass of BaseNode")

        # Create node type info
        node_info = NodeTypeInfo(
            node_class=node_class,
            name=node_name,
            description=description,
            category=category,
            tags=tags,
        )

        # Register the node
        self._nodes[node_name] = node_info

        # Update category index
        if node_info.category not in self._categories:
            self._categories[node_info.category] = []
        if node_name not in self._categories[node_info.category]:
            self._categories[node_info.category].append(node_name)

        # Update tag index
        for tag in node_info.tags:
            if tag not in self._tags:
                self._tags[tag] = []
            if node_name not in self._tags[tag]:
                self._tags[tag].append(node_name)

        logger.info(f"Registered node type: {node_name} ({node_class.__name__})")

    def unregister(self, name: str) -> bool:
        """Unregister a node type.

        Args:
            name: Name of the node type to unregister

        Returns:
            True if the node was unregistered, False if it wasn't found
        """
        if name not in self._nodes:
            return False

        node_info = self._nodes[name]

        # Remove from category index
        if node_info.category in self._categories:
            if name in self._categories[node_info.category]:
                self._categories[node_info.category].remove(name)
            if not self._categories[node_info.category]:
                del self._categories[node_info.category]

        # Remove from tag index
        for tag in node_info.tags:
            if tag in self._tags and name in self._tags[tag]:
                self._tags[tag].remove(name)
                if not self._tags[tag]:
                    del self._tags[tag]

        # Remove the node
        del self._nodes[name]
        logger.info(f"Unregistered node type: {name}")
        return True

    def get_node_class(self, name: str) -> "Optional[type[BaseNode[Any, Any]]]":
        """Get the node class for a given name.

        Args:
            name: Name of the node type

        Returns:
            The node class, or None if not found
        """
        node_info = self._nodes.get(name)
        return node_info.node_class if node_info else None

    def get_node_info(self, name: str) -> Optional[NodeTypeInfo]:
        """Get detailed information about a node type.

        Args:
            name: Name of the node type

        Returns:
            NodeTypeInfo object, or None if not found
        """
        return self._nodes.get(name)

    def list_nodes(
        self, category: Optional[str] = None, tag: Optional[str] = None
    ) -> list[NodeTypeInfo]:
        """List all registered node types, optionally filtered by category or tag.

        Args:
            category: Filter by category (optional)
            tag: Filter by tag (optional)

        Returns:
            List of NodeTypeInfo objects
        """
        nodes = list(self._nodes.values())

        if category:
            nodes = [node for node in nodes if node.category == category]

        if tag:
            nodes = [node for node in nodes if tag in node.tags]

        return sorted(nodes, key=lambda x: x.name)

    def list_categories(self) -> list[str]:
        """List all available categories.

        Returns:
            Sorted list of category names
        """
        return sorted(self._categories.keys())

    def list_tags(self) -> list[str]:
        """List all available tags.

        Returns:
            Sorted list of tag names
        """
        return sorted(self._tags.keys())

    def find_nodes(
        self,
        name_pattern: Optional[str] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        description_pattern: Optional[str] = None,
    ) -> list[NodeTypeInfo]:
        """Find nodes matching various criteria.

        Args:
            name_pattern: Pattern to match in node names (case-insensitive)
            category: Exact category match
            tag: Tag that must be present
            description_pattern: Pattern to match in descriptions (case-insensitive)

        Returns:
            List of matching NodeTypeInfo objects
        """
        nodes = list(self._nodes.values())

        if category:
            nodes = [node for node in nodes if node.category == category]

        if tag:
            nodes = [node for node in nodes if tag in node.tags]

        if name_pattern:
            pattern = name_pattern.lower()
            nodes = [node for node in nodes if pattern in node.name.lower()]

        if description_pattern:
            pattern = description_pattern.lower()
            nodes = [node for node in nodes if pattern in node.description.lower()]

        return sorted(nodes, key=lambda x: x.name)

    def to_dict(self) -> dict[str, Any]:
        """Export registry to dictionary for serialization.

        Returns:
            Dictionary representation of the registry
        """
        return {
            "nodes": {name: info.to_dict() for name, info in self._nodes.items()},
            "categories": dict(self._categories),
            "tags": dict(self._tags),
        }


# Global registry instance
_global_registry = NodeRegistry()


def get_registry() -> NodeRegistry:
    """Get the global node registry instance.

    Returns:
        The global NodeRegistry instance
    """
    return _global_registry


def register_node(
    node_class: "type[BaseNode[Any, Any]]",
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    override: bool = False,
) -> None:
    """Register a node type in the global registry.

    This is a convenience function that uses the global registry instance.

    Args:
        node_class: The node class to register
        name: Human-readable name for the node type
        description: Description of what the node does
        category: Category for organizing nodes
        tags: List of tags for searching and filtering
        override: Whether to override an existing registration
    """
    _global_registry.register(
        node_class=node_class,
        name=name,
        description=description,
        category=category,
        tags=tags,
        override=override,
    )
