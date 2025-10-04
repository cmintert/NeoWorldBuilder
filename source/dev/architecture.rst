Architecture Overview
=====================

Core Philosophy
---------------

NeoWorldBuilder is a sophisticated worldbuilding tool that uses a graph database (Neo4j) to organize creative ideas around four fundamental concepts:

1. **Names** - Unique identifiers for every element
2. **Descriptions** - Rich textual content
3. **Labels** - Categorical classification (Characters, Locations, Events, etc.)
4. **Relations** - Meaningful connections between elements

Service-Oriented Architecture
------------------------------

The application follows a service-oriented pattern with clear separation of concerns:

Core Layer (``src/core/``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Database connectivity and worker threads:

* ``neo4jmodel.py``: Neo4j connection management and query execution
* ``neo4jworkers.py``: QThread workers for async database operations

Service Layer (``src/services/``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Business logic and feature services:

* ``LLMService.py``: AI integration for content generation
* ``WorkerManagerService``: Centralized thread lifecycle management
* ``NameCacheService``: In-memory caching for fast autocomplete
* ``PropertyService``: Dynamic property management
* ``RelationshipTreeService``: Hierarchical relationship visualization
* ``MapService``: Map feature persistence and loading (deprecated)

UI Layer (``src/ui/``)
~~~~~~~~~~~~~~~~~~~~~~~

PyQt6-based interface components:

* ``main_window.py``: Main application window
* ``controller.py``: MVC controller coordinating Model and View
* ``components/``: Reusable UI components (map, calendar, timeline, etc.)
* ``mixins/``: Specialized functionality mixins for the controller

Utils (``src/utils/``)
~~~~~~~~~~~~~~~~~~~~~~~

Shared utilities and helpers:

* ``geometry_handler.py``: WKT geometry manipulation
* ``exporters.py``: Export functionality
* ``validation.py``: Input validation
* ``path_helper.py``: Cross-platform path handling

Key Architectural Patterns
---------------------------

Worker-Based Threading
~~~~~~~~~~~~~~~~~~~~~~

All database operations run in QThread workers to keep UI responsive:

.. code-block:: python

    # Worker types in src/core/neo4jworkers.py
    - QueryWorker: Read operations
    - WriteWorker: Create/Update operations
    - DeleteWorker: Delete operations
    - SuggestionWorker: AI-powered suggestions

All workers:

* Run in separate QThreads
* Communicate via PyQt signals
* Handle their own database connections
* Include retry logic and error handling

Signal/Slot Communication
~~~~~~~~~~~~~~~~~~~~~~~~~

PyQt6 signals for async communication between components:

* UI emits signals for user actions
* Workers emit signals with results
* Controller coordinates signal routing
* Ensures thread-safe UI updates

MVC-like Pattern
~~~~~~~~~~~~~~~~

WorldBuildingController coordinates between:

* **Model**: Neo4jModel (database access)
* **View**: UI components (display and interaction)
* **Controller**: Business logic and coordination

Configuration Management
~~~~~~~~~~~~~~~~~~~~~~~~~

Multi-file JSON configs with environment awareness:

* ``system.json``: Version, environment, encryption keys
* ``database.json``: Neo4j connection settings
* ``logging.json``: Structured logging configuration
* ``ui.json``: UI preferences and settings
* ``limits.json``: Application constraints

Environment detection automatically switches between development and production configs.

Database Architecture
---------------------

Neo4j Graph Database
~~~~~~~~~~~~~~~~~~~~

Primary data store for all worldbuilding elements:

* **Project Isolation**: All nodes tagged with ``_project`` property
* **System Properties**: Automatic ``_created``, ``_modified``, ``_author`` tracking
* **Bidirectional Relationships**: All relationships traversable both ways
* **Stump Nodes**: Automatic placeholder creation for incomplete references

Node Structure
~~~~~~~~~~~~~~

.. code-block:: python

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

Map Component Architecture
--------------------------

Recently Refactored Design
~~~~~~~~~~~~~~~~~~~~~~~~~~

The map component was modularized from a 1,562-line file into focused modules:

.. code-block:: text

    map_component/
    ├── map_tab.py (526 lines) - Main orchestrator
    ├── map_toolbar_manager.py - Toolbar creation
    ├── map_mode_manager.py - Mode state management
    ├── map_event_handler.py - Event processing
    ├── map_feature_loader.py - Database loading
    ├── map_coordinate_utilities.py - Geometry calculations
    ├── graphics/ - Graphics-based rendering system
    │   ├── map_graphics_scene.py
    │   ├── map_graphics_view.py
    │   ├── pin_graphics_item.py
    │   ├── line_graphics_item.py
    │   ├── polygon_graphics_item.py
    │   └── signal_bridge.py - Signal coordination
    └── containers/ - Feature management wrappers
        ├── pin_container.py
        ├── line_container.py
        └── branching_line_container.py

This refactoring demonstrates the preferred pattern: composition with focused, single-responsibility classes.

Error Handling Strategy
-----------------------

* **Structured Logging**: JSON-formatted logs via structlog
* **Graceful Degradation**: Application continues despite non-critical errors
* **User-Friendly Messages**: Technical errors translated for users
* **Comprehensive Try/Except**: All database operations wrapped

Security Considerations
-----------------------

* **Password Encryption**: Uses generated keys stored in system.json
* **Input Validation**: All Neo4j names validated against injection
* **Project Isolation**: Multi-tenant data separation via ``_project`` property
* **Limited Error Details**: Production mode limits exposed information

Development Workflow
--------------------

Building for Distribution
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Build release version
    python deploy.py --build-type release

    # Build with specific version type
    python deploy.py --build-type {nightly,alpha,beta,rc,release}

Running Tests
~~~~~~~~~~~~~

.. code-block:: bash

    # Run all tests
    pytest src/tests/

    # Run specific test file
    pytest src/tests/calendar_test.py

Code Quality Tools
~~~~~~~~~~~~~~~~~~

* flake8 for linting
* black for code formatting
* mypy for type checking (configured)
* pytest for unit testing
