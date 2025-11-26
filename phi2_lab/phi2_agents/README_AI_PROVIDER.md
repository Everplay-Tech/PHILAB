# AI Provider Service

## Overview

The `AIProviderService` is a factory service that centralizes the creation and management of Phi-2 AI agents. It eliminates duplicated agent instantiation code across scripts and provides a clean, configuration-driven API for agent management.

## Features

- **Centralized Agent Creation**: Factory pattern for all agent types
- **Configuration-Driven**: Loads agent configs from `config/agents.yaml`
- **Dependency Injection**: Manages shared resources (model manager, atlas writer, etc.)
- **Service Registry**: Get agents by ID or role
- **Caching**: Optional agent instance caching for performance

## Quick Start

### Basic Usage

```python
from pathlib import Path
from phi2_lab.phi2_agents import AIProviderService
from phi2_lab.phi2_core.config import load_app_config

# Load application configuration
app_config = load_app_config("config/app.yaml")

# Initialize the AI Provider Service
ai_provider = AIProviderService(
    app_config=app_config,
    agents_config_path="config/agents.yaml",
    repo_root=Path.cwd(),
)

# Get agents by ID
architect = ai_provider.get_agent("architect")
experimenter = ai_provider.get_agent("experiment")

# Or get agents by role
atlas_agent = ai_provider.get_agent_by_role("atlas_writer")

# Access shared resources
atlas_writer = ai_provider.atlas_writer
atlas_storage = ai_provider.atlas_storage
model_manager = ai_provider.model_manager
```

### Building All Agents at Once

```python
# Build all configured agents
all_agents = ai_provider.build_all_agents()

# Access individual agents
architect = all_agents["architect"]
atlas_agent = all_agents["atlas"]
```

### Getting Helper Services

```python
# Get an experiment runner with atlas integration
experiment_runner = ai_provider.get_experiment_runner()
```

## API Reference

### Constructor

```python
AIProviderService(
    app_config: AppConfig,
    agents_config_path: str | Path,
    repo_root: Optional[Path] = None,
    context_builder: Optional[ContextBuilder] = None,
    adapter_manager: Optional[AdapterManager] = None,
)
```

**Parameters:**
- `app_config`: Application configuration (model, atlas, etc.)
- `agents_config_path`: Path to agents.yaml configuration file
- `repo_root`: Repository root directory (for resolving paths)
- `context_builder`: Optional shared context builder for all agents
- `adapter_manager`: Optional shared adapter manager for all agents

### Methods

#### `get_agent(agent_id: str, use_cache: bool = True) -> BaseAgent`

Get or create an agent by its ID.

**Parameters:**
- `agent_id`: The unique identifier for the agent (e.g., "architect", "atlas")
- `use_cache`: Whether to return cached instance if available

**Returns:** Fully initialized agent instance

**Raises:** `KeyError` if agent_id is not found in configuration

#### `get_agent_by_role(role: str, use_cache: bool = True) -> BaseAgent`

Get or create an agent by its role.

**Parameters:**
- `role`: The agent's role (e.g., "experiment_runner", "atlas_writer")
- `use_cache`: Whether to return cached instance if available

**Returns:** Fully initialized agent instance

**Raises:** `KeyError` if role is not found in configuration

#### `build_all_agents() -> Dict[str, BaseAgent]`

Build all configured agents at once.

**Returns:** Dictionary mapping agent IDs to fully initialized agent instances

#### `get_experiment_runner() -> ExperimentRunner`

Get an ExperimentRunner instance with atlas writer integration.

**Returns:** Configured ExperimentRunner instance

#### `clear_cache() -> None`

Clear the agent instance cache. Use this if you need to force recreation of agents with updated configurations.

#### `list_available_agents() -> Dict[str, str]`

List all available agents with their descriptions.

**Returns:** Dictionary mapping agent IDs to their descriptions

#### `list_available_roles() -> Dict[str, str]`

List all available roles with their agent IDs.

**Returns:** Dictionary mapping roles to agent IDs

### Properties

- `app_config`: The application configuration
- `model_manager`: Shared Phi2ModelManager instance
- `atlas_storage`: Shared AtlasStorage instance
- `atlas_writer`: Shared AtlasWriter instance
- `context_builder`: Optional shared ContextBuilder
- `adapter_manager`: Optional shared AdapterManager

## Supported Agents

The service automatically creates the correct agent type based on the agent ID:

| Agent ID | Agent Class | Special Dependencies |
|----------|-------------|---------------------|
| `architect` | `ArchitectAgent` | - |
| `experiment` | `ExperimentAgent` | - |
| `atlas` | `AtlasAgent` | `atlas_writer` |
| `compression` | `CompressionAgent` | `register_semantic_code` callback |
| `adapter` | `AdapterAgent` | - |
| *others* | `BaseAgent` | - |

## Configuration

The service loads agent configurations from `config/agents.yaml`:

```yaml
agents:
  architect:
    id: architect
    role: architect
    description: Architectural reasoning specialist.
    system_prompt: |
      You are the Architect Agent for Phi-2 Lab...
    default_lenses: []

  experiment:
    id: experiment
    role: experiment_runner
    description: Experiment spec planner.
    system_prompt: |
      You convert goals into concrete experiment specs...
    default_lenses: []
```

## Migration Guide

### Before (Manual Agent Creation)

```python
from phi2_lab.phi2_agents.architect_agent import ArchitectAgent
from phi2_lab.phi2_agents.atlas_agent import AtlasAgent
from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_atlas.writer import AtlasWriter
from phi2_lab.phi2_core.model_manager import Phi2ModelManager

# Load configs manually
agent_cfgs = _load_agent_configs(args.agents_config)

# Create each agent manually
atlas_storage = AtlasStorage(atlas_path)
atlas_writer = AtlasWriter(atlas_storage)
model_manager = Phi2ModelManager.get_instance(app_cfg.model)

architect = ArchitectAgent(
    agent_cfgs["architect"],
    model_manager
)
atlas_agent = AtlasAgent(
    config=agent_cfgs["atlas"],
    model_manager=model_manager,
    atlas_writer=atlas_writer,
)
# ... repeat for each agent
```

### After (Using AIProviderService)

```python
from phi2_lab.phi2_agents import AIProviderService

# Create the service
ai_provider = AIProviderService(
    app_config=app_cfg,
    agents_config_path=args.agents_config,
    repo_root=repo_root,
)

# Get agents
architect = ai_provider.get_agent("architect")
atlas_agent = ai_provider.get_agent("atlas")
```

**Benefits:**
- ~50 lines of boilerplate code eliminated
- Consistent dependency injection
- Centralized configuration management
- Easier to test and maintain

## Examples

See the updated implementation in:
- `/home/user/PHILAB/phi2_lab/scripts/milestone7_orchestrator.py`

## Advanced Usage

### Custom Context Builder or Adapter Manager

```python
from phi2_lab.phi2_context.context_builder import ContextBuilder
from phi2_lab.phi2_core.adapter_manager import AdapterManager

# Create custom dependencies
context_builder = ContextBuilder(...)
adapter_manager = AdapterManager(...)

# Pass them to the provider
ai_provider = AIProviderService(
    app_config=app_config,
    agents_config_path="config/agents.yaml",
    context_builder=context_builder,
    adapter_manager=adapter_manager,
)

# All agents will use these shared instances
agent = ai_provider.get_agent("architect")
```

### Listing Available Agents and Roles

```python
# List all available agents
agents = ai_provider.list_available_agents()
for agent_id, description in agents.items():
    print(f"{agent_id}: {description}")

# List all available roles
roles = ai_provider.list_available_roles()
for role, agent_id in roles.items():
    print(f"{role} -> {agent_id}")
```

## Notes

- The service uses singleton pattern for the model manager to ensure only one instance is loaded
- Agent instances are cached by default for performance; use `clear_cache()` to force recreation
- Special agent types (Atlas, Compression) receive additional dependencies automatically
- Unknown agent IDs will create a `BaseAgent` instance by default
