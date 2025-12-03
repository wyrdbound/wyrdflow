# HumanInputNode

The `HumanInputNode` enables workflows to pause execution and collect structured input from users via a configurable interface. It supports Pydantic model-based schemas, declarative state mapping, and eliminates boilerplate prep/extract nodes.

> **Note**: This node supports both the modern Pydantic-based API (recommended) and the legacy FieldConfig API. The Pydantic approach leverages standard Python type hints and integrates seamlessly with LangGraph workflows.

## Features

- **Pydantic Model Integration**: Define schemas using standard Pydantic models (recommended)
- **Declarative State Mapping**: Map inputs directly to state paths, no prep/extract nodes needed
- **Legacy FieldConfig Support**: Still supports the original FieldConfig approach
- **Multiple Input Types**: Support for strings, numbers, booleans, and lists
- **Custom Validation**: Leverage Pydantic validators or custom validation functions
- **Pluggable Interfaces**: Default CLI interface with support for custom web/GUI interfaces
- **Rich CLI Experience**: Colored output, help text, and intuitive prompts

## Basic Usage (Recommended)

```python
from pydantic import BaseModel, Field
from wyrdflow.nodes import HumanInputNode

# Define input schema using Pydantic
class UserInfo(BaseModel):
    user_name: str = Field(
        ...,
        json_schema_extra={"prompt": "Enter your name:"}
    )
    age: int = Field(
        default=25,
        ge=0,
        le=120,
        json_schema_extra={"prompt": "Enter your age:"}
    )

# Create node with automatic field generation
input_node = HumanInputNode.from_model(
    model=UserInfo,
    node_id="user_input",
    output_map={
        "user_name": "user.profile.name",
        "age": "user.profile.age"
    }
)
```

## Field Types

### Supported Types

- `str`: Text input
- `int`: Integer numbers
- `float`: Decimal numbers
- `bool`: Yes/no confirmation
- `list[str]`: Multi-line text input (one item per line)

## Defining Input Schemas

### Method 1: Pydantic Models (Recommended)

Use standard Pydantic models with `json_schema_extra` for prompts and help text:

````python
from pydantic import BaseModel, Field

class ContactForm(BaseModel):
    name: str = Field(
        ...,  # Required field
## Custom Validation

### With Pydantic (Recommended)

Use Pydantic validators for clean, declarative validation:

```python
from pydantic import BaseModel, Field, field_validator

class UserInput(BaseModel):
    email: str = Field(..., json_schema_extra={"prompt": "Email address:"})

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Email must contain @ symbol")
        return v

node = HumanInputNode.from_model(UserInput, node_id="input")
````

### With FieldConfig (Legacy)

Validation functions must return a `FieldValidationResult`:

````python
from wyrdflow.nodes import FieldConfig, FieldValidationResult

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
``` )

node = HumanInputNode.from_model(ContactForm, node_id="contact")
````

### Method 2: FieldConfig (Legacy)

The original API using FieldConfig objects is still supported:

```python
from wyrdflow.nodes import HumanInputNode, FieldConfig

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

node = HumanInputNode(node_id="user_input", fields=fields)
```

**FieldConfig attributes:**

- `name`: Field identifier and display name
- `field_type`: Python type for validation
- `prompt`: User-facing question/prompt
- `required`: Whether field must have a value (default: True)
- `validation_fn`: Custom validation function (optional)
- `default_value`: Default if user provides no input (optional)
- `help_text`: Additional guidance for users (optional)

## Custom Validation

## State Mapping

Map input values directly to state paths using `output_map`, eliminating the need for separate prep and extract nodes:

```python
from pydantic import BaseModel, Field

class UserInput(BaseModel):
    user_name: str = Field(..., json_schema_extra={"prompt": "Name:"})
    age: int = Field(..., json_schema_extra={"prompt": "Age:"})

# Map fields to nested state paths
node = HumanInputNode.from_model(
    UserInput,
    node_id="user_input",
    output_map={
        "user_name": "user.profile.name",
        "age": "user.profile.age"
    }
)
```

Without `output_map`, collected fields are stored in `state.data['collected_fields']`.
prompt="Enter email address:",
validation_fn=validate_email
)

````

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
````

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

## Complete Example

```python
import asyncio
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field, field_validator
from typing import TypedDict, Any

from wyrdflow.nodes import HumanInputNode
from wyrdflow.core.state import WorkflowState


# Define input schema
class UserProfile(BaseModel):
    name: str = Field(
        ...,
        json_schema_extra={"prompt": "What is your name?"}
    )

    age: int = Field(
        ...,
        ge=0,
        le=120,
        json_schema_extra={"prompt": "What is your age?"}
    )

    @field_validator('age')
    @classmethod
    def validate_age(cls, v: int) -> int:
        if v < 0 or v > 120:
            raise ValueError("Age must be between 0 and 120")
        return v

    hobbies: list[str] = Field(
        default_factory=list,
        json_schema_extra={
            "prompt": "List your hobbies:",
            "help_text": "Enter one per line, empty line when done"
        }
    )


# Define LangGraph state
class GraphState(TypedDict, total=False):
    user: dict[str, Any]
    workflow_state: dict[str, Any]


async def main():
    # Create node with declarative mapping
    input_node = HumanInputNode.from_model(
        UserProfile,
        node_id="collect_user_info",
        output_map={
            "name": "user.profile.name",
            "age": "user.profile.age",
            "hobbies": "user.interests.hobbies"
        }
    )

    # Build LangGraph workflow
    graph = StateGraph(GraphState)
    graph.add_node("collect_input", input_node.as_langraph_node())
    graph.add_edge("collect_input", END)
    graph.set_entry_point("collect_input")

    workflow = graph.compile()

    # Run workflow
    try:
        # Initialize state
        initial_state = {
            "workflow_state": WorkflowState.create_new().model_dump()
        }

        result = await workflow.ainvoke(initial_state)

        print("\nCollected user information:")
        print(f"Name: {result['user']['profile']['name']}")
        print(f"Age: {result['user']['profile']['age']}")
        print(f"Hobbies: {result['user']['interests']['hobbies']}")

    except KeyboardInterrupt:
        print("\nUser cancelled")


if __name__ == "__main__":
    asyncio.run(main())
```

See `examples/human_input_example.py` for a complete novel plot generator demonstrating all features.
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

if **name** == "**main**":

## API Reference

### HumanInputNode

Main node class for collecting user input.

**Class Methods:**

- `from_model(model, node_id, output_map=None, **kwargs)`: Create node from Pydantic model (recommended)
  - `model`: Pydantic BaseModel defining input fields
  - `node_id`: Unique node identifier
  - `output_map`: Optional mapping from field names to state paths
  - `**kwargs`: Additional BaseNode arguments (input_map, config, etc.)

**Constructor:**

```python
HumanInputNode(
    node_id: str,
    interface: Optional[InputInterface] = None,
    fields: Optional[list[FieldConfig]] = None,
    input_map: Optional[dict[str, str]] = None,
    output_map: Optional[dict[str, str]] = None,
    **kwargs
)
```

### HumanInputNodeInput

Input configuration for HumanInputNode (used when not using `from_model`).

**Attributes:**

- `fields` (list[FieldConfig]): List of fields to collect
- `output_mapping` (Optional[dict[str, str]]): Map field names to state paths (deprecated, use output_map in constructor)
- `max_retry_attempts` (int): Maximum retry attempts per field (default: 3)

### HumanInputNodeOutput

Output from HumanInputNode.

**Attributes:**

- `collected_fields` (dict[str, Any]): Dictionary of collected values
- `fields_collected` (list[str]): List of field names collected
- `execution_id` (str): Unique execution identifier

### FieldConfig (Legacy API)

Configuration for a single input field.

**Attributes:**

- `name` (str): Field identifier
- `field_type` (type): Python type (str, int, float, bool, list[str])
- `prompt` (str): User-facing prompt text
- `required` (bool): Whether field is required (default: True)
- `validation_fn` (Optional[Callable]): Custom validation function
- `default_value` (Optional[Any]): Default value
- `help_text` (Optional[str]): Additional help text

### FieldValidationResult

Result of field validation (for FieldConfig validation_fn).

**Attributes:**

- `is_valid` (bool): Whether validation passed
- `errors` (list[str]): List of validation error messages

### InputInterface

Abstract base class for custom input interfaces.

**Methods:**

- `collect_field(field_config: FieldConfig) -> Any`: Collect a field value
- `show_error(message: str) -> None`: Display error message
- `show_help(message: str) -> None`: Display help text

### RichCLIInterface

Default CLI interface using Rich library.

Provides colored terminal output with interactive prompts.

### RichCLIInterface

Default CLI interface using Rich library.

Provides colored terminal output with interactive prompts.
