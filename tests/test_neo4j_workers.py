from unittest.mock import Mock

import pytest
from PyQt5.QtCore import QThread
from src.main import Neo4jQueryWorker, BaseNeo4jWorker, QueryWorker, WriteWorker, BatchWorker, Neo4jWorkerManager, DeleteWorker
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

def test_delete_worker_initialization(config):
    worker = DeleteWorker(config["uri"], (config["user"], config["password"]), Mock(), "test_node")
    assert worker._uri == config["uri"]
    assert worker._auth == (config["user"], config["password"])
    assert worker.func is not None
    assert worker.args == ("test_node",)

def test_delete_worker_execute_operation(config):
    worker = DeleteWorker(config["uri"], (config["user"], config["password"]), Mock(), "test_node")
    worker.connect = Mock()
    worker.cleanup = Mock()
    worker.func = Mock()

    worker.execute_operation()

    worker.connect.assert_called_once()
    worker.cleanup.assert_called_once()
    worker.func.assert_called_once()

def test_delete_worker_signals(config):
    worker = DeleteWorker(config["uri"], (config["user"], config["password"]), Mock(), "test_node")
    spy = QSignalSpy(worker.delete_finished)

    worker.delete_finished.emit(True)

    assert len(spy) == 1
    assert spy[0] == [True]

def test_query_worker_initialization(config):
    worker = QueryWorker(config["uri"], (config["user"], config["password"]), "MATCH (n) RETURN n")
    assert worker._uri == config["uri"]
    assert worker._auth == (config["user"], config["password"])
    assert worker.query == "MATCH (n) RETURN n"
    assert worker.params == {}

def test_query_worker_execute_operation(config):
    worker = QueryWorker(config["uri"], (config["user"], config["password"]), "MATCH (n) RETURN n")
    worker.connect = Mock()
    worker.cleanup = Mock()
    worker._driver = Mock()
    worker._driver.session.return_value.__enter__.return_value.run.return_value = []

    worker.execute_operation()

    worker.connect.assert_called_once()
    worker.cleanup.assert_called_once()
    worker._driver.session.return_value.__enter__.return_value.run.assert_called_once_with("MATCH (n) RETURN n", {})

def test_write_worker_initialization(config):
    worker = WriteWorker(config["uri"], (config["user"], config["password"]), Mock(), "test_node")
    assert worker._uri == config["uri"]
    assert worker._auth == (config["user"], config["password"])
    assert worker.func is not None
    assert worker.args == ("test_node",)

def test_write_worker_execute_operation(config):
    worker = WriteWorker(config["uri"], (config["user"], config["password"]), Mock(), "test_node")
    worker.connect = Mock()
    worker.cleanup = Mock()
    worker._driver = Mock()
    worker._driver.session.return_value.__enter__.return_value.execute_write = Mock()

    worker.execute_operation()

    worker.connect.assert_called_once()
    worker.cleanup.assert_called_once()
    worker._driver.session.return_value.__enter__.return_value.execute_write.assert_called_once()

def test_batch_worker_initialization(config):
    operations = [("MATCH (n) RETURN n", {})]
    worker = BatchWorker(config["uri"], (config["user"], config["password"]), operations)
    assert worker._uri == config["uri"]
    assert worker._auth == (config["user"], config["password"])
    assert worker.operations == operations

def test_batch_worker_execute_operation(config):
    operations = [("MATCH (n) RETURN n", {})]
    worker = BatchWorker(config["uri"], (config["user"], config["password"]), operations)
    worker.connect = Mock()
    worker.cleanup = Mock()
    worker._driver = Mock()
    worker._driver.session.return_value.__enter__.return_value.run.return_value = []

    worker.execute_operation()

    worker.connect.assert_called_once()
    worker.cleanup.assert_called_once()
    worker._driver.session.return_value.__enter__.return_value.run.assert_called_once_with("MATCH (n) RETURN n", {})
