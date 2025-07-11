# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Tasks

### Running the Application
```bash
# Development mode
python src/main.py

# The application requires Neo4j to be running and configured
```

### Building for Distribution
```bash
# Build release version
python deploy.py --build-type release

# Build with specific version type
python deploy.py --build-type {nightly,alpha,beta,rc,release}
```

### Running Tests
```bash
# Run all tests
pytest src/tests/

# Run specific test file
pytest src/tests/calendar_test.py
```

### Environment Setup
```bash
# Create virtual environment (Python 3.12+ required)
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies from requirements.txt
pip install -r requirements.txt
```

## High-Level Architecture

### Core Philosophy
NeoWorldBuilder is a sophisticated worldbuilding tool that uses a graph database (Neo4j) to organize creative ideas. It's built around four fundamental concepts:
1. **Names** - Unique identifiers for every element
2. **Descriptions** - Rich textual content
3. **Labels** - Categorical classification (Characters, Locations, Events, etc.)
4. **Relations** - Meaningful connections between elements

### Architecture Overview

#### Service-Oriented Architecture
The application follows a service-oriented pattern with clear separation of concerns:
- **Core Layer** (`src/core/`): Database connectivity and worker threads
- **Service Layer** (`src/services/`): Business logic and feature services
- **UI Layer** (`src/ui/`): PyQt6-based interface components
- **Utils** (`src/utils/`): Shared utilities and helpers

#### Key Architectural Patterns
1. **Worker-Based Threading**: All database operations run in QThread workers to keep UI responsive
2. **Signal/Slot Communication**: PyQt6 signals for async communication between components
3. **MVC-like Pattern**: Controller (WorldBuildingController) coordinates between Model (Neo4jModel) and View (UI components)
4. **Configuration Management**: Multi-file JSON configs with environment awareness (dev/prod)

### Database Architecture
- **Neo4j Graph Database**: Primary data store for all worldbuilding elements
- **Project Isolation**: All nodes tagged with `_project` property for multi-project support
- **System Properties**: Automatic tracking of `_created`, `_modified`, `_author` metadata
- **Bidirectional Relationships**: All relationships can be traversed both ways
- **Stump Nodes**: Automatic creation of placeholder nodes for incomplete references

### Threading Model
```python
# Worker types in src/core/neo4jworkers.py:
- QueryWorker: Read operations
- WriteWorker: Create/Update operations  
- DeleteWorker: Delete operations
- SuggestionWorker: AI-powered suggestions
```

All workers:
- Run in separate QThreads
- Communicate via PyQt signals
- Handle their own database connections
- Include retry logic and error handling

### Service Layer Architecture
Key services that power the application:
- **LLMService**: AI integration for content generation
- **WorkerManagerService**: Centralized thread lifecycle management
- **NameCacheService**: In-memory caching for fast autocomplete
- **PropertyService**: Dynamic property management
- **RelationshipTreeService**: Hierarchical relationship visualization
- **AutocompletionService**: Smart name matching
- **MapService**: Map feature persistence and loading

### Configuration System
Multi-file configuration with environment awareness:
- `system.json`: Version, environment, encryption keys
- `database.json`: Neo4j connection settings
- `logging.json`: Structured logging configuration
- `ui.json`: UI preferences and settings
- `limits.json`: Application constraints

Environment detection automatically switches between development and production configs.

### Map Component Architecture (Recently Refactored)
The map component was recently modularized from a 1,562-line file to multiple focused modules:

```
map_component/
├── map_tab.py (526 lines) - Main orchestrator
├── map_toolbar_manager.py - Toolbar creation and management
├── map_mode_manager.py - Mode state and transitions
├── map_event_handler.py - Event processing and handling
├── map_feature_loader.py - Database feature loading
├── map_coordinate_utilities.py - Geometry calculations
└── containers/
    ├── base_map_feature_container.py - Abstract base
    ├── pin_container.py - Pin feature management
    ├── line_container.py - Line/branching line features
    └── branching_line_container.py - Specialized branching wrapper
```

This refactoring demonstrates the preferred pattern for large components: composition with focused, single-responsibility classes.

### Data Model
```python
# Node structure in Neo4j
{
    "name": str,              # Unique identifier
    "description": str,       # Rich text content
    "tags": List[str],        # User-defined tags
    "labels": List[str],      # Categories
    "additional_properties": Dict[str, Any],
    "relationships": List[Tuple],
    # System properties (auto-managed):
    "_created": ISO_timestamp,
    "_modified": ISO_timestamp,
    "_author": str,
    "_project": str
}
```

### Error Handling Strategy
- **Structured Logging**: JSON-formatted logs via structlog
- **Graceful Degradation**: Application continues despite non-critical errors
- **User-Friendly Messages**: Technical errors translated for users
- **Comprehensive Try/Except**: All database operations wrapped

### Security Considerations
- **Password Encryption**: Uses generated keys stored in system.json
- **Input Validation**: All Neo4j names validated against injection
- **Project Isolation**: Multi-tenant data separation via _project property
- **Limited Error Details**: Production mode limits exposed error information

## Important Development Notes

1. **Dependencies Tracked**: requirements.txt now exists for dependency management.

2. **No Linting Configuration**: No .flake8, .pylintrc, or pre-commit hooks configured.

3. **Python Version**: Requires Python 3.12+ (enforced by deploy.py).

4. **Database Required**: Neo4j must be running for the application to start.

5. **Cross-Platform Paths**: Use path helpers from `src/utils/path_helper.py` for Windows/Linux compatibility.

6. **Worker Cleanup**: Always ensure workers are properly terminated to avoid thread leaks.

7. **Signal Naming**: Follow PyQt convention: `signal_name = pyqtSignal()` for custom signals.

8. **Configuration Changes**: Development configs are auto-cleaned during deployment to production.

9. **Testing Approach**: Tests use pytest framework, focus on component-level testing.

10. **Refactoring Pattern**: When refactoring large files, use the map component approach: extract to focused manager classes with clear responsibilities.

11. **Development Tools**: Just note that you got flake8 and black at your disposal.

12. **Import Organization Standards**: All Python files must follow PEP 8 import organization with proper grouping and blank line separation (see Code Quality Standards section below).

13. **Configurable Logging**: Use the map component logging system for debug output instead of print statements (see Logging Standards section below).

## Signal/Slot Communication Patterns

### Map Component Signal Flow
The map component uses a complex signal chain for user interactions. Understanding this flow is critical for debugging UI issues:

#### Feature Click Signal Chain
```
1. Label Click (Base Container) 
   → _emit_container_click_signal()
   → pin_clicked/line_clicked signal

2. Feature Manager
   → Receives container-specific signals
   → Emits unified feature_clicked signal

3. Map Tab  
   → Receives feature_clicked
   → Delegates to event_handler.handle_feature_click()
   → Emits pin_clicked signal

4. Controller (Map Mixin)
   → Receives pin_clicked from map tab
   → _handle_pin_click() loads target node
```

#### Critical Signal Connection Patterns
- **Container Level**: Each feature type (PinContainer, LineContainer) has its own click signal (`pin_clicked`, `line_clicked`)
- **Feature Manager**: Unifies different container signals into a single `feature_clicked` signal
- **Map Tab**: Acts as signal relay between internal components and external controllers
- **Controller**: Final destination that performs actual node navigation

#### Map Tab Creation Gotcha
**IMPORTANT**: There are two different `_ensure_map_tab_exists()` methods:

1. **MapMixin Version** (`src/ui/mixins/mapmixin.py:12`): 
   - Called when loading existing MAP nodes from database
   - Sets up ALL signal connections including `pin_clicked` and `line_created`

2. **UI Version** (`src/ui/main_window.py:1140`):
   - Called when user types "MAP" into labels field in real-time
   - Must mirror ALL connections from MapMixin version
   - Missing connections here break feature navigation

**Rule**: Both map tab creation paths must have identical signal connections, or UI features will appear to work but not function correctly.

#### Debugging Signal Issues
When UI interactions don't work:
1. **Use logging instead of prints**: `logger.debug("Signal emitted: signal_name")` to trace signal emission through the chain
2. Check both map tab creation methods have matching signal connections  
3. Verify container-specific signals (pin_clicked vs line_clicked) are properly routed
4. Ensure feature manager unifies signals correctly
5. Confirm controller methods are actually connected to tab signals
6. **Set debug logging**: `MAP_COMPONENT_LOG_LEVEL=DEBUG` to see detailed signal flow information

## Code Quality Standards

### Import Organization (Updated 2025)

All Python files **must** follow PEP 8 import organization with strict grouping and separation:

```python
# Standard library imports
import json
import os
from typing import Optional, List, Dict, Tuple

# Third-party library imports
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from structlog import get_logger

# Local/project imports
from utils.geometry_handler import GeometryHandler
from ui.components.dialogs import SomeDialog

# Relative imports (within same package)
from .utils.coordinate_transformer import CoordinateTransformer
from .base_feature_container import BaseFeatureContainer
```

**Rules:**
1. **Three distinct groups** separated by blank lines
2. **Alphabetical ordering** within each group
3. **Combine imports** from same module: `from PyQt6.QtCore import Qt, pyqtSignal` not separate lines
4. **No unused imports** - remove any imports not referenced in the code
5. **Prefer specific imports**: `from module import SpecificClass` over `import module`

**Tools:**
- Use `python3 -m py_compile filename.py` to verify syntax after import changes
- All map component files have been standardized as of Phase 2 improvements

### Logging Standards (New)

**Never use `print()` statements for debug output.** Use the configurable logging system instead:

```python
# For map component files - use configurable logging
from .utils.map_logger import get_map_logger
logger = get_map_logger(__name__)

# For other files - use standard structlog
from structlog import get_logger
logger = get_logger(__name__)

# Usage in code
logger.debug("Detailed debug information")
logger.info("General information") 
logger.warning("Warning message")
logger.error("Error message")
```

**Configuration:**
- Set log level via environment variable: `MAP_COMPONENT_LOG_LEVEL=DEBUG`
- Supported levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- Default level: `INFO` (configurable in `src/config/logging.json`)
- Zero performance impact when debug logging disabled

**Benefits:**
- Runtime configurability without code changes
- Structured logging with JSON format support
- Performance optimization in production
- Consistent with existing structlog infrastructure

## Development Workflow Updates

### File Modification Checklist

When modifying any file in the codebase:

1. **Check imports** - Ensure proper PEP 8 organization
2. **Remove debug prints** - Replace with appropriate logging calls
3. **Verify syntax** - Run `python3 -m py_compile filename.py`
4. **Update CLAUDE.md** - Document any new patterns or significant changes
5. **Test functionality** - Ensure no regressions introduced

### Map Component Specific Guidelines

The map component (`src/ui/components/map_component/`) has undergone significant architectural improvements:

**Recent Improvements:**
- **Automatic Point Reclassification**: Branching points automatically convert from red to blue when connections drop below 3 (implemented in `edit_mode.py`)
- **Property Setters Fixed**: All branch creation properties now have proper setters (`map_tab.py`)
- **Import Organization**: Standardized across all 24 Python files (Phase 2)
- **Configurable Logging**: Implemented (`utils/map_logger.py`) with environment variable support (Phase 2)
- **Code Cleanup**: 112 debug print statements removed, unused imports eliminated (Phase 2)

**Key Files:**
- `utils/map_logger.py` - Configurable logging infrastructure
- All container files - Standardized import organization
- All manager files - Clean, maintainable import structure