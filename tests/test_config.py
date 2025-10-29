"""Tests for NodeConfig class."""

import pytest

from wyrdflow.core import NodeConfig


class TestNodeConfig:
    """Test suite for NodeConfig class."""

    def test_default_configuration(self):
        """Test default NodeConfig values."""
        config = NodeConfig()

        assert config.retry_attempts == 3
        assert config.retry_delay == 1.0
        assert config.retry_exponential_base == 2.0
        assert config.retry_max_delay == 60.0
        assert config.timeout == 300.0
        assert config.enable_logging is True
        assert config.node_settings == {}

    def test_custom_configuration(self):
        """Test NodeConfig with custom values."""
        config = NodeConfig(
            retry_attempts=5,
            retry_delay=2.0,
            retry_exponential_base=3.0,
            retry_max_delay=120.0,
            timeout=600.0,
            enable_logging=False,
            node_settings={"custom": "value"},
        )

        assert config.retry_attempts == 5
        assert config.retry_delay == 2.0
        assert config.retry_exponential_base == 3.0
        assert config.retry_max_delay == 120.0
        assert config.timeout == 600.0
        assert config.enable_logging is False
        assert config.node_settings == {"custom": "value"}

    def test_get_node_setting(self):
        """Test get_node_setting method."""
        config = NodeConfig(node_settings={"test_key": "test_value"})

        # Test existing key
        assert config.get_node_setting("test_key") == "test_value"

        # Test non-existing key with default
        assert config.get_node_setting("missing_key") is None
        assert config.get_node_setting("missing_key", "default") == "default"

    def test_set_node_setting(self):
        """Test set_node_setting method."""
        config = NodeConfig()

        # Set a new setting
        config.set_node_setting("new_key", "new_value")
        assert config.node_settings["new_key"] == "new_value"
        assert config.get_node_setting("new_key") == "new_value"

        # Update existing setting
        config.set_node_setting("new_key", "updated_value")
        assert config.get_node_setting("new_key") == "updated_value"

    def test_update_node_settings(self):
        """Test update_node_settings method."""
        config = NodeConfig(node_settings={"existing": "value"})

        updates = {"key1": "value1", "key2": "value2", "existing": "updated_value"}

        config.update_node_settings(updates)

        assert config.get_node_setting("key1") == "value1"
        assert config.get_node_setting("key2") == "value2"
        assert config.get_node_setting("existing") == "updated_value"

    def test_validation_constraints(self):
        """Test that configuration values are validated."""
        # Test negative retry attempts
        with pytest.raises(ValueError):
            NodeConfig(retry_attempts=-1)

        # Test negative delay
        with pytest.raises(ValueError):
            NodeConfig(retry_delay=-1.0)

        # Test exponential base less than 1
        with pytest.raises(ValueError):
            NodeConfig(retry_exponential_base=0.5)

        # Test negative max delay
        with pytest.raises(ValueError):
            NodeConfig(retry_max_delay=-1.0)

        # Test zero or negative timeout
        with pytest.raises(ValueError):
            NodeConfig(timeout=0.0)

        with pytest.raises(ValueError):
            NodeConfig(timeout=-10.0)

    def test_no_extra_fields_allowed(self):
        """Test that extra fields are not allowed."""
        with pytest.raises(ValueError):
            NodeConfig(invalid_field="should_fail")  # type: ignore[call-arg]

    def test_model_serialization(self):
        """Test that NodeConfig can be serialized."""
        config = NodeConfig(retry_attempts=2, node_settings={"test": "value"})

        serialized = config.model_dump()

        assert serialized["retry_attempts"] == 2
        assert serialized["node_settings"]["test"] == "value"

        # Test that we can recreate from serialized data
        recreated = NodeConfig(**serialized)
        assert recreated.retry_attempts == 2
        assert recreated.get_node_setting("test") == "value"
