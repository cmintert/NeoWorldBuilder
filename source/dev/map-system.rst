Map System Architecture
=======================

Overview
--------

The map component is one of the most complex subsystems in NeoWorldBuilder. It provides interactive map visualization with support for pins, lines, branching lines, and polygons.

Signal/Slot Communication
-------------------------

Map Component Signal Flow
~~~~~~~~~~~~~~~~~~~~~~~~~~

Understanding the signal chain is critical for debugging UI issues:

Feature Click Signal Chain
^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. **Label Click (Base Container)**

   * Container emits container-specific signal (``pin_clicked``, ``line_clicked``)

2. **Feature Manager**

   * Receives container signals
   * Emits unified ``feature_clicked`` signal

3. **Map Tab**

   * Receives ``feature_clicked``
   * Delegates to ``event_handler.handle_feature_click()``
   * Emits ``pin_clicked`` signal

4. **Controller (Map Mixin)**

   * Receives ``pin_clicked`` from map tab
   * ``_handle_pin_click()`` loads target node

Critical Signal Connection Patterns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Container Level**: Each feature type has its own click signal
* **Feature Manager**: Unifies different container signals
* **Map Tab**: Acts as signal relay between components
* **Controller**: Final destination for node navigation

Map Tab Creation
~~~~~~~~~~~~~~~~

**IMPORTANT**: There are two ``_ensure_map_tab_exists()`` methods:

1. **MapMixin Version** (``src/ui/mixins/mapmixin.py:12``):

   * Called when loading existing MAP nodes from database
   * Sets up ALL signal connections

2. **UI Version** (``src/ui/main_window.py:1140``):

   * Called when user types "MAP" into labels field
   * Delegates to MapMixin version for consistency

**Rule**: Both paths must have identical signal connections.

Graphics System
---------------

QGraphicsView Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~

The map uses Qt's Graphics View Framework:

* **QGraphicsScene**: Manages map items and coordinate system
* **QGraphicsView**: Provides viewport and zoom controls
* **QGraphicsItem**: Individual map features (pins, lines, polygons)

Coordinate System
~~~~~~~~~~~~~~~~~

* Scene coordinates = Original image pixel coordinates (1:1 mapping)
* View coordinates = Scaled/transformed for display
* All features stored in original coordinates for precision

Graphics Items
~~~~~~~~~~~~~~

**PinGraphicsItem**
^^^^^^^^^^^^^^^^^^^

* Renders SVG pin icon
* Clickable for node navigation
* Shows label on hover
* Supports drag-and-drop repositioning

**LineGraphicsItem**
^^^^^^^^^^^^^^^^^^^^

* Renders simple lines (LineString WKT)
* Supports branching lines (MultiLineString WKT)
* Edit mode with draggable control points
* Configurable style (color, width, pattern)

**PolygonGraphicsItem**
^^^^^^^^^^^^^^^^^^^^^^^

* Renders filled polygons
* Configurable fill and outline
* Click to navigate to region node
* Renders beneath pins and lines (z-order)

Signal Bridge
~~~~~~~~~~~~~

The ``GraphicsSignalBridge`` connects QGraphicsItem signals to PyQt signals:

.. code-block:: python

    class GraphicsSignalBridge(QObject):
        # Feature interaction signals
        feature_clicked = pyqtSignal(str)

        # Pin-specific signals
        pin_clicked = pyqtSignal(str)
        pin_moved = pyqtSignal(str, int, int)

        # Line-specific signals
        line_clicked = pyqtSignal(str)
        line_geometry_changed = pyqtSignal(str, list)

        # Polygon-specific signals
        polygon_clicked = pyqtSignal(str)
        polygon_geometry_changed = pyqtSignal(str, list)

**Why needed**: QGraphicsItem doesn't inherit from QObject, so can't use pyqtSignal directly.

QGIS-like Branching Line System (MVP)
--------------------------------------

Branch-Level Interaction
~~~~~~~~~~~~~~~~~~~~~~~~~

The system provides professional GIS-level interaction with branching lines, enabling road networks and river systems.

**Branch Click Detection**

Located in ``LineGraphicsItem._detect_clicked_branch()``:

.. code-block:: python

    def _detect_clicked_branch(self, pos: QPointF) -> Optional[Tuple[int, str, Optional[str]]]:
        """Returns (branch_index, stable_id, assigned_node)"""
        # Point-to-line-segment distance algorithm
        # 10-pixel tolerance for user-friendly clicking
        # Returns full branch information including assignments

**Branch-Specific Signal**

Added to ``GraphicsSignalBridge``:

.. code-block:: python

    branch_clicked = pyqtSignal(str, str, object)  # node_name, stable_id, assigned_node

Signal emitted when user clicks specific branch, not just the line.

**Smart Navigation Flow**

.. code-block:: python

    # User clicks on branch
    LineGraphicsItem.mousePressEvent()
        → _detect_clicked_branch(pos)
        → _emit_branch_click_signal(branch_idx, stable_id, assigned_node)
        → signal_bridge.branch_clicked.emit(...)
        → map_tab_adapter connection
        → Navigate to assigned_node (or fallback to main node if unassigned)

Visual Feedback System
~~~~~~~~~~~~~~~~~~~~~~

**Branch Labels**

``LineGraphicsItem._draw_branch_labels()``:

* Displays "→ NodeName" at branch midpoints
* Color-coded backgrounds matching branch colors
* Scale-responsive font sizing
* Only shown for assigned branches

**Interactive Tooltips**

``LineGraphicsItem._update_branch_tooltip()``:

* Updates on hover: "Branch 1 → Northern_Village\\nClick to navigate"
* Shows assignment status and navigation instructions
* Real-time updates based on mouse position

**Junction Markers**

``LineGraphicsItem._draw_branching_point()`` enhanced with:

* Red circular badges showing connection count (for 3+ branches)
* Scale-responsive badge sizing
* Visual distinction of network topology

Network Topology Features
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Junction Connectivity Query**

``LineGraphicsItem._show_connected_features()``:

Right-click junction → Context menu "Show Connected (N branches)" → Dialog displays:

* Junction coordinates
* Connected branch count
* Each branch's: stable_id, assignment, point count

**Example Output**:

.. code-block:: text

    Junction at (450, 320)
    Connected branches: 4

    Branch details:
      • Main Stem → City_Center (8 points)
      • Branch 1 → Northern_District (5 points)
      • Branch 2 → Western_Port (6 points)
      • Branch 3 (unassigned) (4 points)

Dialog Validation
~~~~~~~~~~~~~~~~~

``BranchingLineFeatureDialog.accept_dialog()`` improvements:

1. **Primary Target Validation**: Red border + error message if empty
2. **Branch Assignment Warning**: Confirmation dialog if no assignments
3. **Visual Feedback**: Clears styling when valid

Data Model
~~~~~~~~~~

Branch assignments stored as flat properties in Neo4j:

.. code-block:: cypher

    (Map)-[:SHOWS {
        geometry: "MULTILINESTRING ((0 0, 100 100), (100 100, 200 50))",
        geometry_type: "MultiLineString",
        branch_count: 2,
        branch_main_stem: "City_Center",
        branch_branch_1: "Northern_District",
        style_color: "#FF0000",
        style_width: 2
    }]->(RoadNetwork)

Stable IDs ensure consistent branch identification across sessions.

Use Cases
~~~~~~~~~

1. **Road Networks**: Highway systems with exit branches to cities
2. **River Systems**: Main rivers with tributary branches to sources
3. **Rail Networks**: Main lines with branch lines to terminals
4. **Trade Routes**: Primary routes with branches to trading posts

Feature Management
------------------

GraphicsFeatureManager
~~~~~~~~~~~~~~~~~~~~~~

Central manager for all map features:

* ``add_pin_feature(node_name, x, y)``
* ``add_line_feature(node_name, points, style)``
* ``add_branching_line_feature(node_name, branches, style)``
* ``add_polygon_feature(node_name, points, style)``
* ``remove_feature(node_name)``
* ``clear_all_features()``

Storage
~~~~~~~

Features stored as Neo4j relationships:

.. code-block:: cypher

    (Map)-[:SHOWS {
        geometry: "POINT (100 200)",
        geometry_type: "Point"
    }]->(Location)

    (Map)-[:SHOWS {
        geometry: "LINESTRING (0 0, 100 100, 200 50)",
        geometry_type: "LineString",
        style_color: "#FF0000",
        style_width: 3
    }]->(Road)

    (Map)-[:SHOWS {
        geometry: "POLYGON ((0 0, 100 0, 100 100, 0 100, 0 0))",
        geometry_type: "Polygon",
        fill_color: "#4a90e2",
        fill_opacity: 0.3
    }]->(Region)

WKT Geometry Format
~~~~~~~~~~~~~~~~~~~

All geometries use Well-Known Text (WKT) format via Shapely library:

* **POINT**: Single location
* **LINESTRING**: Simple line
* **MULTILINESTRING**: Branching line with multiple segments
* **POLYGON**: Closed area with optional holes

Geometry Handler Utilities:

* ``create_point(x, y)`` → WKT
* ``create_line(points)`` → WKT
* ``create_multi_line(branches)`` → WKT
* ``create_polygon(points)`` → WKT
* ``get_coordinates(wkt)`` → Python data structures

Edit Mode System
----------------

Mode Management
~~~~~~~~~~~~~~~

The ``MapModeManager`` handles exclusive mode states:

* **View Mode** (default): Navigate and click features
* **Pin Placement**: Add new pins
* **Line Drawing**: Draw simple lines
* **Branching Line Drawing**: Draw complex routes
* **Polygon Drawing**: Define regions
* **Edit Mode**: Modify existing features

Mode Transitions
~~~~~~~~~~~~~~~~

Modes are mutually exclusive - only one active at a time:

.. code-block:: python

    def enforce_mode_exclusivity(self, active_mode: str):
        """Ensure only the specified mode is active."""
        modes = {
            'pin_placement_active': False,
            'line_drawing_active': False,
            'branching_line_drawing_active': False,
            'polygon_drawing_active': False,
            'edit_mode_active': False
        }
        modes[active_mode] = True
        for mode, state in modes.items():
            setattr(self, mode, state)

Branching Line System
---------------------

Stable IDs
~~~~~~~~~~

Branches are identified by stable IDs to support persistence:

* ``branch_1``, ``branch_2``, etc. for main branches
* IDs preserved across edits and saves
* Node assignments stored as ``branch_branch_1: "NodeName"``

Automatic Reclassification
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Branch points are automatically reclassified:

* **Blue points**: 3+ connections (true branch points)
* **Red points**: < 3 connections (end points or waypoints)
* Happens automatically after adding/removing branches

Snapping System
~~~~~~~~~~~~~~~

Press **S** in edit mode to toggle snapping:

* Configurable snap distance threshold
* Visual feedback when snap triggers
* Helps align features precisely
* Per-line toggle support

Recent Improvements
-------------------

2025 Updates
~~~~~~~~~~~~

**Automatic Point Reclassification**

* Branching points auto-convert red ↔ blue based on connection count
* Implemented in ``edit_mode.py``

**Property Setters Fixed**

* All branch creation properties now have proper setters in ``map_tab.py``

**Import Organization**

* Standardized across all 24 map component Python files (Phase 2)
* PEP 8 compliance with proper grouping

**Configurable Logging**

* Implemented in ``utils/map_logger.py``
* Environment variable support: ``MAP_COMPONENT_LOG_LEVEL=DEBUG``

**Code Cleanup**

* 112 debug print statements removed
* Unused imports eliminated
* Polygon feature support fully implemented

Debugging Tips
--------------

Signal Issues
~~~~~~~~~~~~~

When UI interactions don't work:

1. Use logging: ``logger.debug("Signal emitted: signal_name")``
2. Check both map tab creation methods have matching connections
3. Verify container-specific signals route correctly
4. Ensure feature manager unifies signals
5. Confirm controller methods connected to tab signals
6. Set debug logging: ``MAP_COMPONENT_LOG_LEVEL=DEBUG``

Performance
~~~~~~~~~~~

* Monitor feature count (100+ features may slow edit mode)
* Check coordinate conversion logging (should be minimal)
* Watch for signal recursion (infinite loops)
* Profile with cProfile if rendering slows

Testing
~~~~~~~

Test files available:

* ``test_pin_graphics.py``
* ``test_line_graphics.py``
* ``test_graphics_integration.py``
* ``test_full_integration.py``
