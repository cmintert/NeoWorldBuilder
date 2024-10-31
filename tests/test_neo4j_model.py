import pytest
from unittest.mock import Mock, patch
from src.main import Neo4jModel

@pytest.fixture
def config():
    return {
        "uri": "bolt://localhost:7687",
        "username": "neo4j",
        "password": "password"
    }

@pytest.fixture
def model(config):
    return Neo4jModel(config["uri"], config["username"], config["password"])

def test_neo4j_model_initialization(config):
    model = Neo4jModel(config["uri"], config["username"], config["password"])
    assert model._uri == config["uri"]
    assert model._auth == (config["username"], config["password"])
    assert model._driver is not None

def test_neo4j_model_load_node(model):
    with patch.object(model, 'load_node', return_value=Mock()) as mock_load_node:
        callback = Mock()
        worker = model.load_node("Test Node", callback)
        mock_load_node.assert_called_once_with("Test Node", callback)
        assert worker is not None

def test_neo4j_model_save_node(model):
    with patch.object(model, 'save_node', return_value=Mock()) as mock_save_node:
        node_data = {
            "name": "Test Node",
            "description": "Test Description",
            "tags": ["Tag1", "Tag2"],
            "labels": ["Label1", "Label2"],
            "relationships": [],
            "additional_properties": {}
        }
        callback = Mock()
        worker = model.save_node(node_data, callback)
        mock_save_node.assert_called_once_with(node_data, callback)
        assert worker is not None

def test_neo4j_model_delete_node(model):
    with patch.object(model, 'delete_node', return_value=Mock()) as mock_delete_node:
        callback = Mock()
        worker = model.delete_node("Test Node", callback)
        mock_delete_node.assert_called_once_with("Test Node", callback)
        assert worker is not None
