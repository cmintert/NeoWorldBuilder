Contributing
============

Development Setup
-----------------

Prerequisites
~~~~~~~~~~~~~

* Python 3.12+
* Neo4j database
* Git
* Code editor (PyCharm recommended)

Clone and Setup
~~~~~~~~~~~~~~~

.. code-block:: bash

    # Clone repository
    git clone https://github.com/cmintert/NeoWorldBuilder.git
    cd NeoWorldBuilder

    # Create virtual environment
    python -m venv .venv
    .venv\Scripts\activate  # Windows
    source .venv/bin/activate  # Linux/Mac

    # Install dependencies
    pip install -r requirements.txt

    # Run application
    python src/main.py

Code Quality Standards
----------------------

Import Organization
~~~~~~~~~~~~~~~~~~~

All Python files must follow PEP 8 import organization:

.. code-block:: python

    # Standard library imports
    import json
    import os
    from typing import Optional, List

    # Third-party library imports
    from PyQt6.QtCore import Qt, pyqtSignal
    from structlog import get_logger

    # Local/project imports
    from utils.geometry_handler import GeometryHandler

    # Relative imports
    from .utils.coordinate_transformer import CoordinateTransformer

**Rules**:

* Three distinct groups separated by blank lines
* Alphabetical ordering within each group
* Combine imports from same module
* No unused imports
* Prefer specific imports over wildcard

Logging Standards
~~~~~~~~~~~~~~~~~

Never use ``print()`` for debug output. Use structured logging:

.. code-block:: python

    # For map component files
    from .utils.map_logger import get_map_logger
    logger = get_map_logger(__name__)

    # For other files
    from structlog import get_logger
    logger = get_logger(__name__)

    # Usage
    logger.debug("Detailed debug information")
    logger.info("General information")
    logger.warning("Warning message")
    logger.error("Error message", error=str(e), exc_info=True)

Configuration:

* Set log level: ``MAP_COMPONENT_LOG_LEVEL=DEBUG``
* Supported levels: DEBUG, INFO, WARNING, ERROR
* Default: INFO

Development Workflow
--------------------

Branching Strategy
~~~~~~~~~~~~~~~~~~

* ``master``: Stable releases
* ``develop``: Integration branch for features
* ``feature/*``: Individual feature branches
* ``bugfix/*``: Bug fix branches

Making Changes
~~~~~~~~~~~~~~

1. Create feature branch from ``develop``
2. Make changes following code quality standards
3. Test changes locally
4. Update documentation if needed
5. Run tests: ``pytest src/tests/``
6. Create pull request to ``develop``

File Modification Checklist
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When modifying files:

1. Check imports - PEP 8 organization
2. Remove debug prints - use logging
3. Verify syntax: ``python3 -m py_compile filename.py``
4. Update CLAUDE.md for significant changes
5. Test functionality

Git Commit Guidelines
~~~~~~~~~~~~~~~~~~~~~

Use descriptive commit messages:

.. code-block:: text

    Fix polygon feature saving and loading

    Fixed two critical bugs preventing polygon map features from working:

    1. PolygonGraphicsItem QObject conversion error:
       - Removed invalid pyqtSignal from non-QObject class
       - Added feature_type attribute for signal bridge

    2. Polygon WKT coordinate extraction error:
       - Fixed GeometryHandler to use geometry.exterior.coords

    Files changed:
    - src/ui/components/map_component/graphics/polygon_graphics_item.py
    - src/utils/geometry_handler.py

Important Notes:

* NEVER update git config
* NEVER run destructive commands (force push, hard reset)
* NEVER skip hooks unless explicitly requested
* NEVER amend others' commits
* Only commit when explicitly asked

Testing
-------

Running Tests
~~~~~~~~~~~~~

.. code-block:: bash

    # All tests
    pytest src/tests/

    # Specific test file
    pytest src/tests/calendar_test.py

    # With coverage
    pytest --cov=src src/tests/

Writing Tests
~~~~~~~~~~~~~

* Use pytest framework
* Focus on component-level testing
* Mock external dependencies (Neo4j, PyQt6)
* Test edge cases and error handling

Building Documentation
----------------------

The documentation uses Sphinx with auto-generated API docs.

Build Docs
~~~~~~~~~~

.. code-block:: bash

    # Full rebuild
    make rebuild

    # Just HTML
    make html

    # Clean and build
    make clean-api clean-html html

Auto-generate API Docs
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Regenerate API documentation
    make apidoc

Configuration
~~~~~~~~~~~~~

* ``source/conf.py``: Sphinx configuration
* ``source/index.rst``: Documentation root
* ``source/guide/``: User guides
* ``source/dev/``: Developer documentation
* ``source/api/``: Auto-generated (not tracked in git)

Architecture Guidelines
-----------------------

When Adding Features
~~~~~~~~~~~~~~~~~~~~

Follow the service-oriented pattern:

1. **Service Layer**: Business logic in ``src/services/``
2. **UI Layer**: User interface in ``src/ui/components/``
3. **Mixin**: Controller integration in ``src/ui/mixins/``
4. **Worker**: Database operations in ``src/core/neo4jworkers.py``

Example - Adding a New Map Feature:

1. Create graphics item (``src/ui/components/map_component/graphics/``)
2. Add dialog (``src/ui/components/map_component/dialogs/``)
3. Update feature manager (``graphics_feature_manager.py``)
4. Add signal bridge support (``signal_bridge.py``)
5. Update event handler (``map_event_handler.py``)
6. Add geometry handling (``src/utils/geometry_handler.py``)

Refactoring Pattern
~~~~~~~~~~~~~~~~~~~

When refactoring large files:

* Extract focused manager classes
* Single responsibility principle
* Use composition over inheritance
* Follow map component refactoring example (1562 → multiple focused files)

Common Patterns
---------------

Signal/Slot Pattern
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # Emit signal
    self.feature_created.emit(feature_type, node_name)

    # Connect signal
    self.event_handler.pin_created.connect(self.pin_created.emit)

    # Define signal
    pin_created = pyqtSignal(str, str, dict)

Worker Pattern
~~~~~~~~~~~~~~

.. code-block:: python

    # Create worker
    worker = QueryWorker(query, params)

    # Connect signals
    worker.results.connect(self._handle_results)
    worker.error.connect(self._handle_error)

    # Start worker
    self.worker_manager.start_worker(worker)

Getting Help
------------

* **Documentation**: Read this documentation
* **Code Examples**: Look at existing similar features
* **CLAUDE.md**: Project-specific guidance
* **Issues**: Report bugs via GitHub issues

Pull Request Process
--------------------

1. Ensure all tests pass
2. Update documentation for new features
3. Follow code quality standards
4. Provide clear description of changes
5. Reference related issues
6. Request review from maintainers

Thank you for contributing to NeoWorldBuilder!
