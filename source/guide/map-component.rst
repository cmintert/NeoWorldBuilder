Map Component Guide
===================

Overview
--------

The Map Component allows you to create interactive maps for your worldbuilding project. Add locations, routes, regions, and other geographic features to visualize your world.

Creating a Map Node
-------------------

To use the map component:

1. Create a new node or load an existing one
2. Add the **MAP** label to the node
3. The **Map** tab will automatically appear
4. Load a map image to begin

Loading Map Images
------------------

Supported Formats
~~~~~~~~~~~~~~~~~

* PNG
* JPG/JPEG
* BMP
* GIF

Image Requirements
~~~~~~~~~~~~~~~~~~

* Maximum recommended size: 4096x4096 pixels
* Images are displayed at 1:1 pixel scale
* Zoom controls allow viewing at different scales

Map Features
------------

Pins
~~~~

**Purpose**: Mark specific locations (cities, landmarks, points of interest)

**How to Add**:

1. Click the **Pin** button in the toolbar
2. Click on the map where you want to place the pin
3. Enter the node name for this location
4. The pin will be saved as a relationship to that node

**Navigation**:

* Click a pin to load its associated node
* Pins are clickable in both view and edit modes

Lines
~~~~~

**Purpose**: Draw roads, rivers, borders, or other linear features

**How to Add**:

1. Click the **Line** button in the toolbar
2. Click points on the map to define the line
3. Press **Enter** to complete the line
4. Choose color, width, and pattern
5. Enter the node name for this feature

**Editing**:

* Enter **Edit Mode** to modify line points
* Drag control points to reshape lines
* Press **S** to toggle snapping mode

Branching Lines
~~~~~~~~~~~~~~~

**Purpose**: Create complex route networks with branching paths

**How to Add**:

1. Click the **Branching Line** button
2. Draw the main route with multiple clicks
3. Press **Enter** to save the first branch
4. Continue adding branches as needed

**Branch Creation**:

* Enter **Edit Mode**
* Press **B** while hovering over a line
* Click to set the branch start point
* Click again to create the branch

**Automatic Reclassification**:

* Branch points with 3+ connections shown in blue
* Points with <3 connections automatically turn red
* This helps visualize the branch structure

Polygons
~~~~~~~~

**Purpose**: Define regions, territories, or areas

**How to Add**:

1. Click the **Polygon** button
2. Click points to define the polygon boundary
3. Press **Enter** or **Tab** to complete
4. Choose fill color, opacity, and outline style
5. Enter the node name for this region

**Styling**:

* Fill color and opacity
* Outline color, width, and pattern
* Polygons render beneath pins and lines

Keyboard Shortcuts
------------------

Map Navigation
~~~~~~~~~~~~~~

* **Scroll**: Zoom in/out
* **Middle Mouse Button**: Pan the map
* **Ctrl + Scroll**: Fine zoom control

Drawing Mode
~~~~~~~~~~~~

* **Enter**: Complete current feature
* **Tab**: Toggle polygon drawing mode
* **Escape**: Cancel current operation

Edit Mode
~~~~~~~~~

* **B**: Start branch creation mode
* **S**: Toggle snapping for precise alignment
* **Delete**: Remove selected control point

Edit Mode
---------

Activating Edit Mode
~~~~~~~~~~~~~~~~~~~~

Click the **Edit** button in the toolbar to:

* Modify existing lines and branching lines
* Reposition control points
* Add new branches to existing lines
* Remove unwanted points

Snapping
~~~~~~~~

Press **S** in edit mode to enable/disable snapping:

* Helps align features precisely
* Configurable snap distance
* Visual feedback when snap triggers

Technical Details
-----------------

Coordinate System
~~~~~~~~~~~~~~~~~

* Map uses original image pixel coordinates
* All features stored in WKT (Well-Known Text) format
* Supports precise float coordinates for accuracy

Data Storage
~~~~~~~~~~~~

Map features are stored as Neo4j relationships:

* **Relationship Type**: SHOWS
* **Direction**: Map node → Feature node
* **Properties**: WKT geometry + style properties

Example::

    (Map)-[:SHOWS {
        geometry: "POLYGON ((100 100, 200 100, 200 200, 100 200, 100 100))",
        geometry_type: "Polygon",
        fill_color: "#4a90e2",
        fill_opacity: 0.3
    }]->(Region)

Performance Tips
----------------

* Use reasonably sized images (< 4096x4096)
* Limit extremely complex polygons (< 100 points)
* Edit mode may slow with 100+ features
* Consider splitting very dense maps into multiple map nodes
