import pytest
from unittest.mock import Mock, patch
from PyQt6.QtCore import QTimer, QStringListModel
from src.main import WorldBuildingController, WorldBuildingUI, Neo4jModel, Config

@pytest.fixture
def config():
    return Config("src/config.json")

@pytest.fixture
def model(config):
    return Neo4jModel(config.NEO4J_URI, config.NEO4J_USERNAME, config.NEO4J_PASSWORD)

@pytest.fixture
def ui():
    return Mock(spec=WorldBuildingUI)

@pytest.fixture
def controller(ui, model, config):
    return WorldBuildingController(ui, model, config)

def test_worldbuilding_controller_initialization(controller):
    assert controller.ui is not None
    assert controller.model is not None
    assert controller.config is not None

def test_worldbuilding_controller_load_node_data(controller):
    with patch.object(controller.model, 'load_node', return_value=Mock()) as mock_load_node:
        controller.ui.name_input.text.return_value = "Test Node"
        controller.load_node_data()
        mock_load_node.assert_called_once_with("Test Node", controller._handle_node_data)

def test_worldbuilding_controller_save_node(controller):
    with patch.object(controller.model, 'save_node', return_value=Mock()) as mock_save_node:
        controller.ui.name_input.text.return_value = "Test Node"
        controller.ui.description_input.toPlainText.return_value = "Test Description"
        controller.ui.labels_input.text.return_value = "Label1, Label2"
        controller.ui.tags_input.text.return_value = "Tag1, Tag2"
        controller.ui.properties_table.rowCount.return_value = 0
        controller.ui.relationships_table.rowCount.return_value = 0
        controller.save_node()
        mock_save_node.assert_called_once()

def test_worldbuilding_controller_delete_node(controller):
    with patch.object(controller.model, 'delete_node', return_value=Mock()) as mock_delete_node:
        controller.ui.name_input.text.return_value = "Test Node"
        with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.Yes):
            controller.delete_node()
            mock_delete_node.assert_called_once_with("Test Node", controller._handle_delete_success)
