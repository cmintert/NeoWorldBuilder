import requests
import logging
from typing import Optional, Dict, Any, Callable, List
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox


class LLMService:
    """Service for LLM integration with OpenAI-compatible APIs including LM Studio."""

    def __init__(self, config, node_operations):
        self.config = config
        self.node_operations = node_operations
        self.api_key = self.config.get("llm.api_key", "")

        # Handle base URL format to avoid double-slash issues
        base_url = self.config.get("llm.base_url", "http://localhost:5555")
        self.base_url = base_url.rstrip("/")  # Remove trailing slash if present

        self.model = self.config.get("llm.model", "mythomax-l2-13b")
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
        """
        Send the description to LLM with optional context from neighboring nodes.

        Args:
            node_name: Current node's name
            description: Current node description
            depth: How many levels of connected nodes to include (0=none)
            callback: Function to call with result or error
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
        """
        Recursively fetch connected nodes and format as context.

        Args:
            node_name: The name of the starting node
            depth: How deep to traverse the graph

        Returns:
            Formatted string containing node context information
        """
        visited = set()
        context_parts = []

        def collect_node_info(name: str, current_depth: int, rel_path: str = ""):
            if current_depth < 0 or name in visited:
                return

            visited.add(name)

            # Get node data
            try:
                node = self.node_operations.get_node_by_name(name)
                if not node:
                    return

                # Format node info
                prefix = f"{rel_path} -> " if rel_path else ""
                node_info = [
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
                    target = (
                        rel[1]
                        if isinstance(rel, tuple) and len(rel) > 1
                        else rel.get("target")
                    )
                    rel_type = (
                        rel[0]
                        if isinstance(rel, tuple) and len(rel) > 0
                        else rel.get("type")
                    )
                    if target and rel_type:
                        new_path = (
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
