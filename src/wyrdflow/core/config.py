"""Configuration classes for Wyrdflow nodes."""

from abc import ABC
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class NodeSpecificConfig(BaseModel, ABC):
    """Abstract base class for node-specific configuration.

    Each node type can define its own configuration schema by inheriting
    from this class. This enables type-safe configuration with validation
    while maintaining the flexibility for each node type to have its own
    specific settings.

    Example:
        ```python
        class HTTPNodeConfig(NodeSpecificConfig):
            url: str
            method: str = "GET"
            headers: dict[str, str] = Field(default_factory=dict)
            timeout: float = 30.0
        ```
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=True,
    )


# Type variable for node-specific configuration
NodeConfigType = TypeVar("NodeConfigType", bound=NodeSpecificConfig)


class NodeConfig(BaseModel):
    """Configuration for node execution behavior.

    This class contains shared configuration options that apply to all nodes,
    such as retry logic, timeouts, and logging settings. It also supports
    type-safe node-specific configuration through the node_config field.

    Attributes:
        retry_attempts: Number of times to retry on failure (default: 3)
        retry_delay: Initial delay between retries in seconds (default: 1.0)
        retry_exponential_base: Base for exponential backoff (default: 2.0)
        retry_max_delay: Maximum delay between retries in seconds (default: 60.0)
        timeout: Maximum execution time in seconds (default: 300.0)
        enable_logging: Whether to enable structured logging (default: True)
        enable_output_pinning: Whether output pinning is enabled for testing (default: False)
        pinned_output: Pinned output data to use instead of executing (default: None)
        node_config: Type-safe node-specific configuration
        node_settings: Legacy key-value pairs for node-specific settings (deprecated)
    """

    # Retry configuration
    retry_attempts: int = Field(
        default=3, ge=0, description="Number of times to retry on failure"
    )
    retry_delay: float = Field(
        default=1.0, ge=0.0, description="Initial delay between retries in seconds"
    )
    retry_exponential_base: float = Field(
        default=2.0, ge=1.0, description="Base for exponential backoff calculation"
    )
    retry_max_delay: float = Field(
        default=60.0, ge=0.0, description="Maximum delay between retries in seconds"
    )

    # Execution configuration
    timeout: float = Field(
        default=300.0, gt=0.0, description="Maximum execution time in seconds"
    )

    # Observability configuration
    enable_logging: bool = Field(
        default=True, description="Whether to enable structured logging"
    )

    # Output pinning for testing
    enable_output_pinning: bool = Field(
        default=False, description="Whether output pinning is enabled for testing"
    )
    pinned_output: Optional[Any] = Field(
        default=None, description="Pinned output data to use instead of executing"
    )

    # Type-safe node-specific configuration
    node_config: Optional[NodeSpecificConfig] = Field(
        default=None, description="Type-safe node-specific configuration"
    )

    # Legacy node-specific settings (deprecated in favor of node_config)
    node_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Node-specific configuration as key-value pairs (deprecated)",
    )

    model_config = ConfigDict(
        # Don't allow extra fields to keep config clean
        extra="forbid",
        # Validate assignments to catch configuration errors early
        validate_assignment=True,
        # Use enum values in serialization
        use_enum_values=True,
    )

    def get_node_setting(self, key: str, default: Any = None) -> Any:
        """Get a node-specific setting with optional default value.

        Args:
            key: The setting key to retrieve
            default: Default value if key is not found

        Returns:
            The setting value or default if not found
        """
        return self.node_settings.get(key, default)

    def set_node_setting(self, key: str, value: Any) -> None:
        """Set a node-specific setting.

        Args:
            key: The setting key to set
            value: The value to set
        """
        self.node_settings[key] = value

    def update_node_settings(self, settings: dict[str, Any]) -> None:
        """Update multiple node-specific settings at once.

        Args:
            settings: Dictionary of settings to update
        """
        self.node_settings.update(settings)

    def pin_output(self, output_data: Any) -> None:
        """Pin output data for testing purposes.

        When output is pinned, the node will return this data instead of
        executing its normal logic. This is useful for testing scenarios
        where you want to skip expensive operations like LLM calls or API requests.

        Args:
            output_data: The data to return instead of executing the node
        """
        self.enable_output_pinning = True
        self.pinned_output = output_data

    def unpin_output(self) -> None:
        """Remove output pinning, allowing normal node execution."""
        self.enable_output_pinning = False
        self.pinned_output = None

    def is_output_pinned(self) -> bool:
        """Check if output is currently pinned.

        Returns:
            True if output is pinned, False otherwise
        """
        return self.enable_output_pinning and self.pinned_output is not None


# Type alias for common case
BasicNodeConfig = NodeConfig


class TypedNodeConfig(BaseModel, Generic[NodeConfigType]):
    """A typed version of NodeConfig that provides type safety for node-specific config.

    This class combines shared configuration with strongly-typed node-specific
    configuration. Use this when you want full type safety for your node configuration.

    Example:
        ```python
        class HTTPNodeConfig(NodeSpecificConfig):
            url: str
            method: str = "GET"

        # Type-safe configuration
        config = TypedNodeConfig[HTTPNodeConfig](
            retry_attempts=5,
            node_config=HTTPNodeConfig(url="https://api.example.com", method="POST")
        )
        ```
    """

    # Shared configuration (same as NodeConfig)
    retry_attempts: int = Field(
        default=3, ge=0, description="Number of times to retry on failure"
    )
    retry_delay: float = Field(
        default=1.0, ge=0.0, description="Initial delay between retries in seconds"
    )
    retry_exponential_base: float = Field(
        default=2.0, ge=1.0, description="Base for exponential backoff calculation"
    )
    retry_max_delay: float = Field(
        default=60.0, ge=0.0, description="Maximum delay between retries in seconds"
    )
    timeout: float = Field(
        default=300.0, gt=0.0, description="Maximum execution time in seconds"
    )
    enable_logging: bool = Field(
        default=True, description="Whether to enable structured logging"
    )
    enable_output_pinning: bool = Field(
        default=False, description="Whether output pinning is enabled for testing"
    )
    pinned_output: Optional[Any] = Field(
        default=None, description="Pinned output data to use instead of executing"
    )

    # Strongly-typed node-specific configuration
    node_config: NodeConfigType = Field(
        description="Type-safe node-specific configuration"
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=True,
    )

    def pin_output(self, output_data: Any) -> None:
        """Pin output data for testing purposes."""
        self.enable_output_pinning = True
        self.pinned_output = output_data

    def unpin_output(self) -> None:
        """Remove output pinning, allowing normal node execution."""
        self.enable_output_pinning = False
        self.pinned_output = None

    def is_output_pinned(self) -> bool:
        """Check if output is currently pinned."""
        return self.enable_output_pinning and self.pinned_output is not None
