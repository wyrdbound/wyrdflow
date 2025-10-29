"""Configuration classes for Wyrdflow nodes."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeConfig(BaseModel):
    """Configuration for node execution behavior.

    This class contains the basic configuration options that apply to all nodes,
    such as retry logic, timeouts, and logging settings. Node-specific settings
    should be stored in the node_settings field or as a separate configuration
    object.

    Attributes:
        retry_attempts: Number of times to retry on failure (default: 3)
        retry_delay: Initial delay between retries in seconds (default: 1.0)
        retry_exponential_base: Base for exponential backoff (default: 2.0)
        retry_max_delay: Maximum delay between retries in seconds (default: 60.0)
        timeout: Maximum execution time in seconds (default: 300.0)
        enable_logging: Whether to enable structured logging (default: True)
        node_settings: Node-specific configuration as key-value pairs
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

    # Node-specific settings
    node_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Node-specific configuration as key-value pairs",
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
