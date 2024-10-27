from unittest.mock import Mock

import pytest
from PyQt5.QtCore import QThread
from src.main import Neo4jQueryWorker, BaseNeo4jWorker, QueryWorker, Neo4jWorkerManager
import pytest
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtTest import QSignalSpy
import time

# This runs before each test
@pytest.fixture
def config():
    # Create test configuration
    return {
        "uri": "bolt://localhost:7687",
        "user": "neo4j",
        "password": "neo4j"
    }
