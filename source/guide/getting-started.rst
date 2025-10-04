Getting Started
===============

Installation
------------

Prerequisites
~~~~~~~~~~~~~

* Python 3.12 or higher
* Neo4j database (4.x or 5.x)
* Windows, Linux, or macOS

Install Dependencies
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Create virtual environment
   python -m venv .venv

   # Activate virtual environment
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac

   # Install dependencies
   pip install -r requirements.txt

Configure Neo4j
~~~~~~~~~~~~~~~

1. Install Neo4j Desktop or Docker
2. Create a new database
3. Configure connection in ``src/config/database.json``

Running the Application
-----------------------

Development Mode
~~~~~~~~~~~~~~~~

.. code-block:: bash

   python src/main.py

The application will connect to Neo4j and display the main interface.

First Steps
-----------

Creating Your First Node
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Enter a name in the **Name** field
2. Add a description in the rich text editor
3. Add labels to categorize your node (e.g., "Character", "Location")
4. Click **Save** to create the node

Adding Relationships
~~~~~~~~~~~~~~~~~~~~

1. With a node loaded, scroll to the **Relationships** section
2. Click **Add Relationship**
3. Select relationship type and target node
4. Add optional properties to the relationship

Working with Maps
~~~~~~~~~~~~~~~~~

1. Add the "MAP" label to a node
2. A **Map** tab will appear
3. Load a map image
4. Add pins, lines, and polygons to mark locations
