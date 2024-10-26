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


def test_base_worker_signals():
    worker = BaseNeo4jWorker(config)
    assert hasattr(worker, 'error_occurred')
    assert hasattr(worker, 'progress_updated')

@pytest.fixture
def config():
    return Mock()

@pytest.fixture
def worker():
    return Mock()

@pytest.fixture
def worker_manager(config):
    return Neo4jWorkerManager(config)

def creates_and_stores_worker(worker_manager, worker):
    worker_class = Mock(return_value=worker)
    created_worker = worker_manager.create_worker(worker_class)
    assert created_worker == worker
    assert worker in worker_manager.active_workers

def cleans_up_finished_worker(worker_manager, worker):
    worker_manager.active_workers.add(worker)
    worker_manager._cleanup_worker(worker)
    assert worker not in worker_manager.active_workers

def cancels_all_active_workers(worker_manager, worker):
    worker_manager.active_workers.add(worker)
    worker_manager.cancel_all()
    worker.cancel.assert_called_once()
    worker.wait.assert_called_once()
    assert not worker_manager.active_workers