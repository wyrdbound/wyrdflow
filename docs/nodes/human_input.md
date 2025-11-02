# HumanInputNode

The `HumanInputNode` enables workflows to pause execution and collect structured input from users via a configurable interface. It supports multiple field types, custom validation, and flexible state mapping.

## Features

- **Dynamic Field Configuration**: Define any number of fields with custom types and validation
- **Multiple Input Types**: Support for strings, numbers, booleans, and lists
- **Custom Validation**: Per-field validation functions with helpful error messages
- **Pluggable Interfaces**: Default CLI interface with support for future web/GUI interfaces
- **State Path Mapping**: Flexible mapping of inputs to nested state structures
- **Rich CLI Experience**: Colored output, help text, and intuitive prompts

## Basic Usage

```python
from wyrdflow import HumanInputNode, HumanInputNodeInput, FieldConfig

# Define input fields
fields = [
    FieldConfig(
        name="user_name",
        field_type=str,
        prompt="Enter your name:",
        required=True
    ),
    FieldConfig(
        name="age",
        field_type=int,
        prompt="Enter your age:",
        default_value=25
    )
]

# Create input configuration
input_config = HumanInputNodeInput(fields=fields)

# Create node
input_node = HumanInputNode(node_id="user_input")
```

## Field Types

### Supported Types

- `str`: Text input
- `int`: Integer numbers
- `float`: Decimal numbers
- `bool`: Yes/no confirmation
- `list[str]`: Multi-line text input (one item per line)

### Field Configuration

Each field supports:

- `name`: Field identifier and display name
- `field_type`: Python type for validation
- `prompt`: User-facing question/prompt
- `required`: Whether field must have a value (default: True)
- `validation_fn`: Custom validation function (optional)
- `default_value`: Default if user provides no input (optional)
- `help_text`: Additional guidance for users (optional)

## Custom Validation

Validation functions must return a `FieldValidationResult` with validity status and error messages:

```python
from wyrdflow import FieldConfig, FieldValidationResult

def validate_email(email: str) -> FieldValidationResult:
    if "@" not in email:
        return FieldValidationResult(
            is_valid=False,
            errors=["Email must contain @ symbol"]
        )
    return FieldValidationResult(is_valid=True)

field = FieldConfig(
    name="email",
    field_type=str,
    prompt="Enter email address:",
    validation_fn=validate_email
)
```

## State Mapping

Control where input values are stored in workflow state using dot notation:

```python
from wyrdflow import HumanInputNodeInput, FieldConfig

input_config = HumanInputNodeInput(
    fields=fields,
    output_mapping={
        "user_name": "user.profile.name",
        "age": "user.profile.age"
    }
)
```

Without mapping, all inputs are stored under `{node_id}_input`.

### Nested State Structure

The node automatically creates nested dictionaries as needed:

```python
# This mapping:
output_mapping={
    "genre": "book.metadata.genre",
    "title": "book.metadata.title"
}

# Creates state structure:
state.data = {
    "book": {
        "metadata": {
            "genre": "sci-fi",
            "title": "My Novel"
        }
    }
}
```

## Error Handling

- **Validation Errors**: Fields retry up to 3 times (configurable) before failing
- **User Cancellation**: CTRL+C raises `UserCancelledError`
- **Required Fields**: Empty required fields cause validation failure
- **Type Conversion**: Invalid types (e.g., "abc" for int) trigger retry

### Retry Configuration

```python
input_config = HumanInputNodeInput(
    fields=fields,
    max_retry_attempts=5  # Allow 5 attempts per field
)
```

## Interface Customization

Create custom interfaces for different environments:

```python
from wyrdflow import InputInterface, FieldConfig
from typing import Any

class WebInterface(InputInterface):
    """Web-based input collection."""

    def collect_field(self, field_config: FieldConfig) -> Any:
        # Implement web-based collection
        pass

    def show_error(self, message: str) -> None:
        # Display error in web UI
        pass

    def show_help(self, message: str) -> None:
        # Display help in web UI
        pass

# Use custom interface
from wyrdflow import HumanInputNode

node = HumanInputNode(
    node_id="input",
    interface=WebInterface()
)
```

## Complete Example

```python
import asyncio
from uuid import uuid4
from wyrdflow import (
    HumanInputNode,
    HumanInputNodeInput,
    FieldConfig,
    FieldValidationResult,
    WorkflowState,
    NodeContext
)

def validate_age(age: int) -> FieldValidationResult:
    """Validate age is reasonable."""
    if age < 0 or age > 120:
        return FieldValidationResult(
            is_valid=False,
            errors=["Age must be between 0 and 120"]
        )
    return FieldValidationResult(is_valid=True)

async def main():
    # Define fields
    fields = [
        FieldConfig(
            name="name",
            field_type=str,
            prompt="What is your name?",
            required=True
        ),
        FieldConfig(
            name="age",
            field_type=int,
            prompt="What is your age?",
            validation_fn=validate_age,
            default_value=25
        ),
        FieldConfig(
            name="hobbies",
            field_type=list[str],
            prompt="List your hobbies:",
            help_text="Enter one per line, empty line when done"
        )
    ]

    # Configure input collection
    input_config = HumanInputNodeInput(
        fields=fields,
        output_mapping={
            "name": "user.profile.name",
            "age": "user.profile.age",
            "hobbies": "user.interests.hobbies"
        }
    )

    # Create node
    node = HumanInputNode(node_id="collect_user_info")

    # Create workflow state and context
    workflow_id = uuid4()
    workflow_run_id = uuid4()

    state = WorkflowState(
        workflow_id=workflow_id,
        workflow_run_id=workflow_run_id
    )

    context = NodeContext(
        workflow_id=workflow_id,
        workflow_run_id=workflow_run_id,
        node_id="collect_user_info"
    )

    # Execute
    try:
        result = await node.execute(input_config, context, state)

        print(f"Collected {len(result.fields_collected)} fields")
        print(f"Name: {state.get('user.profile.name')}")
        print(f"Age: {state.get('user.profile.age')}")
        print(f"Hobbies: {state.get('user.interests.hobbies')}")

    except KeyboardInterrupt:
        print("User cancelled")

if __name__ == "__main__":
    asyncio.run(main())
```

See `examples/human_input_example.py` for a complete novel plot generator that demonstrates all features.

## API Reference

### FieldConfig

Configuration for a single input field.

**Attributes:**

- `name` (str): Field identifier
- `field_type` (type): Python type (str, int, float, bool, list[str])
- `prompt` (str): User-facing prompt text
- `required` (bool): Whether field is required (default: True)
- `validation_fn` (Optional[Callable]): Custom validation function
- `default_value` (Optional[Any]): Default value
- `help_text` (Optional[str]): Additional help text

### HumanInputNodeInput

Input configuration for HumanInputNode.

**Attributes:**

- `fields` (list[FieldConfig]): List of fields to collect
- `output_mapping` (Optional[dict[str, str]]): Map field names to state paths
- `max_retry_attempts` (int): Maximum retry attempts per field (default: 3)

### HumanInputNodeOutput

Output from HumanInputNode.

**Attributes:**

- `collected_fields` (dict[str, Any]): Dictionary of collected values
- `fields_collected` (list[str]): List of field names collected
- `execution_id` (str): Unique execution identifier

### FieldValidationResult

Result of field validation.

**Attributes:**

- `is_valid` (bool): Whether validation passed
- `errors` (list[str]): List of validation error messages

### InputInterface

Abstract base class for input interfaces.

**Methods:**

- `collect_field(field_config: FieldConfig) -> Any`: Collect a field value
- `show_error(message: str) -> None`: Display error message
- `show_help(message: str) -> None`: Display help text

### RichCLIInterface

Default CLI interface using Rich library.

Provides colored terminal output with interactive prompts.
