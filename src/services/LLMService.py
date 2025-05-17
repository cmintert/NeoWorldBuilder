import requests
import logging
from typing import Optional, Dict, Any, Callable, List, Set, Tuple, Union, TypedDict

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox


class NodeType(TypedDict, total=False):
    """A type definition for nodes in the graph database.

    Attributes:
        name (str): The unique name identifier of the node.
        labels (List[str]): A list of labels/categories assigned to the node.
        tags (List[str]): A list of tags associated with the node.
        description (str): The textual description of the node.
        relationships (List[Union[Tuple[str, str], Dict[str, str]]]): List of relationships
            to other nodes. Can be either tuples of (type, target) or dictionaries with
            'type' and 'target' keys.
    """
    name: str
    labels: List[str]
    tags: List[str]
    description: str
    relationships: List[Union[Tuple[str, str], Dict[str, str]]]


class LLMService:
    """Service for integrating with OpenAI-compatible Language Model APIs.

    This service handles communication with LLM APIs, including LM Studio and other
    OpenAI-compatible endpoints. It provides functionality for enhancing node descriptions
    using AI and managing context-aware content generation.

    Attributes:
        config (Any): Configuration object containing LLM settings.
        node_operations (Any): Service for performing node operations.
        api_key (str): Authentication key for the LLM API.
        base_url (str): Base URL for the LLM API endpoint.
        model (str): Name of the language model to use.
    """

    def __init__(self, config: Any, node_operations: Any) -> None:
        """Initialize the LLM service with configuration and node operations.

        Args:
            config: Configuration object containing LLM settings including API key,
                base URL, and model name.
            node_operations: Service object for performing node-related operations
                in the graph database.
        """
        self.config: Any = config
        self.node_operations: Any = node_operations
        self.api_key: str = self.config.get("llm.api_key", "")

        # Handle base URL format to avoid double-slash issues
        base_url: str = self.config.get("llm.base_url", "http://localhost:5555")
        self.base_url: str = base_url.rstrip("/")  # Remove trailing slash if present

        self.model: str = self.config.get("llm.model", "mythomax-l2-13b")
        logging.debug(
            f"LLM Service initialized with URL: {self.base_url}, model: {self.model}"
        )

    def enhance_description(
        self,
        node_name: str,
        description: str,
        callback: Callable[[str, Optional[str]], None],
        depth: int = 0,
    ) -> None:
        """Enhances a node's description using the LLM API with contextual awareness.

        This method sends the current node's description to the LLM API along with optional
        context from neighboring nodes to generate an enhanced, more detailed description
        while maintaining the original style and format.

        Args:
            node_name (str): The name of the node whose description should be enhanced.
            description (str): The current description of the node.
            callback (Callable[[str, Optional[str]], None]): A callback function that takes
                two arguments: the enhanced description (str) and an optional error message
                (str). The first argument will be None if there's an error.
            depth (int, optional): The number of levels of connected nodes to include as
                context. Defaults to 0 (no context).

        Note:
            The callback function is called with (enhanced_text, None) on success,
            or (None, error_message) on failure.

        Raises:
            No exceptions are raised directly; all errors are passed to the callback.
        """
        try:
            prompt = description

            # If depth > 0, fetch and add context from connected nodes
            if depth > 0:
                context = self._get_node_context(node_name, depth)
                if context:
                    prompt = (
                        f"Node information:\n\n{context}\n\nCurrent "
                        f"node description:\n\n{description}\n\nEnhance this description while maintaining the same style and format. Add more details and make it more engaging."
                    )
            else:
                prompt = (
                    f"Node name: {node_name}\n\nCurrent "
                    f"description:\n\n{description}\n\nEnhance this description while maintaining the same style and format. Add more details and make it more engaging."
                )

            headers = {"Content-Type": "application/json"}

            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 500,
            }

            # Ensure the URL format is correct
            endpoint_url = f"{self.base_url}/v1/chat/completions"

            logging.debug(f"Making LLM request to: {endpoint_url}")
            logging.debug(f"Payload: {payload}")

            response = requests.post(
                endpoint_url, headers=headers, json=payload, timeout=60
            )

            response.raise_for_status()
            result = response.json()
            logging.debug(f"LLM response: {result}")

            # Handle different response formats
            try:
                if "choices" in result and len(result["choices"]) > 0:
                    completion = result["choices"][0]["message"]["content"]
                else:
                    # Try alternative formats that might be returned by LM Studio
                    completion = result.get(
                        "response",
                        result.get("content", result.get("output", str(result))),
                    )

                # Combine original with completion
                # Only use the generated content, not the original + generated
                enhanced_text = completion
                callback(enhanced_text, None)
            except Exception as format_error:
                logging.error(
                    f"LLM response format error: {format_error}, response: {result}"
                )
                callback(None, f"Failed to parse LLM response: {format_error}")

        except requests.exceptions.RequestException as req_error:
            logging.error(f"LLM request error: {req_error}")
            callback(None, f"LLM API request failed: {req_error}")
        except Exception as e:
            logging.error(f"LLM service error: {e}")
            callback(None, str(e))

    def _get_node_context(self, node_name: str, depth: int) -> str:
        """Recursively fetches and formats context information from connected nodes.

        This internal method traverses the node graph starting from the given node,
        collecting information about connected nodes up to the specified depth.
        It handles both incoming and outgoing relationships and formats the information
        in a human-readable format.

        Args:
            node_name (str): The name of the starting node from which to gather context.
            depth (int): The maximum number of relationship hops to traverse when
                gathering context. A depth of 0 means only the starting node.

        Returns:
            str: A formatted string containing information about the node and its
                connected nodes, including names, labels, tags, and relationship paths.
                Returns an empty string if no context could be gathered.

        Note:
            The method uses an internal visited set to prevent cycles in the graph
            traversal and handles various relationship formats (tuples and dicts).
        """
        visited: Set[str] = set()
        context_parts: List[str] = []

        def collect_node_info(
            name: str, current_depth: int, rel_path: str = ""
        ) -> None:
            """Recursively collects and formats information about nodes and their relationships.

            Args:
                name (str): Name of the current node being processed.
                current_depth (int): Current depth in the traversal, decrements with each hop.
                rel_path (str, optional): String representing the relationship path taken
                    to reach this node. Defaults to empty string for the starting node.
            """
            if current_depth < 0 or name in visited:
                return

            visited.add(name)

            # Get node data
            try:
                node: Optional[NodeType] = self.node_operations.get_node_by_name(name)
                if not node:
                    return

                # Format node info
                prefix: str = f"{rel_path} -> " if rel_path else ""
                node_info: List[str] = [
                    f"{prefix}Node: {node['name']}",
                    (
                        f"Labels: {', '.join(node['labels'])}"
                        if node.get("labels")
                        else ""
                    ),
                    f"Tags: {', '.join(node['tags'])}" if node.get("tags") else "",
                    (
                        f"Brief: {node['description'][:100]}..."
                        if node.get("description")
                        else ""
                    ),
                ]
                context_parts.append("\n".join(filter(None, node_info)))

                # Stop if we've reached max depth
                if current_depth == 0:
                    return

                # Process relationships
                for rel in node.get("relationships", []):
                    target: Optional[str] = (
                        rel[1]
                        if isinstance(rel, tuple) and len(rel) > 1
                        else rel.get("target")
                    )
                    rel_type: Optional[str] = (
                        rel[0]
                        if isinstance(rel, tuple) and len(rel) > 0
                        else rel.get("type")
                    )
                    if target and rel_type:
                        new_path: str = (
                            f"{rel_path} -[{rel_type}]"
                            if rel_path
                            else f"-[{rel_type}]"
                        )
                        collect_node_info(target, current_depth - 1, new_path)
            except Exception as e:
                logging.error(f"Error processing node {name}: {e}")
                # Continue with other nodes

        # Start collection from the root node
        collect_node_info(node_name, depth)

        return "\n\n".join(context_parts)
