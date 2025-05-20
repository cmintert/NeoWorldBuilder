import logging
from typing import Optional, Dict, Any, Callable, List, Set, Tuple, Union, TypedDict
import os
from dotenv import load_dotenv
import requests


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
        load_dotenv()  # Load environment variables from .env file
        self.config: Any = config
        self.node_operations: Any = node_operations
        self.api_key: str = os.getenv("OPENAI_API_KEY")

        # Handle base URL format to avoid double-slash issues
        self.base_url: str = os.getenv("OPENAI_BASE_URL")

        self.model: str = os.getenv("OPENAI_MODEL")
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
        """Wrapper method that calls the template-based enhancement with default parameters.

        This method preserves backward compatibility while using the template system.

        Args:
            node_name (str): The name of the node whose description should be enhanced.
            description (str): The current description of the node.
            callback (Callable[[str, Optional[str]], None]): A callback function.
            depth (int, optional): The number of levels of connected nodes to include as context.
        """
        # Use the quick template as default for quick enhancement
        template_id = "quick"
        focus_type = "general"
        custom_instructions = ""

        # Delegate to the template-based method
        self.enhance_description_with_template(
            node_name,
            description,
            template_id,
            focus_type,
            depth,
            custom_instructions,
            callback,
        )

    def _get_node_context(self, node_name: str, depth: int) -> str:
        """Recursively fetches and formats context information from connected nodes.

        Args:
            node_name (str): The name of the starting node from which to gather context.
            depth (int): The maximum number of relationship hops to traverse.

        Returns:
            str: A formatted string containing information about the node and its
                connected nodes, with HTML stripped from descriptions.
        """
        visited: Set[str] = set()
        context_parts: List[str] = []

        def strip_html(html_text: str) -> str:
            """Remove HTML tags from text."""
            if not html_text:
                return ""
            import re

            # Remove HTML tags
            text = re.sub(r"<[^>]+>", " ", html_text)
            # Remove doctype and other declarations
            text = re.sub(r"<!DOCTYPE[^>]+>", "", text)
            # Normalize whitespace
            text = re.sub(r"\s+", " ", text).strip()
            return text

        def collect_node_info(
            name: str, current_depth: int, rel_path: str = ""
        ) -> None:
            """Recursively collects and formats information about nodes and relationships.

            Args:
                name (str): Name of the current node being processed.
                current_depth (int): Current depth in the traversal.
                rel_path (str, optional): Relationship path string.
            """
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

                # Get a clean, HTML-stripped description
                description = node.get("description", "")
                clean_description = strip_html(description)
                brief = (
                    clean_description[:150] + "..."
                    if len(clean_description) > 150
                    else clean_description
                )

                node_info = [
                    f"{prefix}Node: {node['name']}",
                    (
                        f"Labels: {', '.join(node['labels'])}"
                        if node.get("labels")
                        else ""
                    ),
                    f"Tags: {', '.join(node['tags'])}" if node.get("tags") else "",
                    f"Brief: {brief}" if brief else "",
                ]
                context_parts.append("\n".join(filter(None, node_info)))

                # Stop if we've reached max depth
                if current_depth == 0:
                    return

                # Process relationships with the new format
                for rel in node.get("relationships", []):
                    target = rel.get("target")
                    rel_type = rel.get("type")
                    direction = rel.get("direction")

                    if target and rel_type:
                        arrow = "->" if direction == "OUTGOING" else "<-"
                        new_path = (
                            f"{rel_path} -[{rel_type}]{arrow}"
                            if rel_path
                            else f"-[{rel_type}]{arrow}"
                        )
                        collect_node_info(target, current_depth - 1, new_path)

            except Exception as e:
                logging.error(f"Error processing node {name} for context: {e}")
                # Continue with other nodes

        # Start collection from the root node
        collect_node_info(node_name, depth)

        return "\n\n".join(context_parts)

    # Add a property for the template service
    @property
    def prompt_template_service(self):
        """Gets the prompt template service used for template-based LLM requests.

        Returns:
            Any: The prompt template service instance used by this LLM service.
        """
        return self._prompt_template_service

    @prompt_template_service.setter
    def prompt_template_service(self, service):
        """Sets the prompt template service for template-based LLM requests.

        Args:
            service: The prompt template service instance to be used by this LLM service.
        """
        self._prompt_template_service = service

    def enhance_description_with_template(
        self,
        node_name: str,
        description: str,
        template_id: str,
        focus_type: str,
        context_depth: int,
        custom_instructions: str,
        callback: Callable[[str, Optional[str]], None],
    ) -> None:
        """Enhances a node's description using a template-based approach with focus."""
        try:
            # Validate that template service is available
            if not self._prompt_template_service:
                callback("", "Prompt template service not available")
                return

            # Get node context if depth > 0
            context = ""
            if context_depth > 0:
                logging.debug(
                    f"Gathering context with depth {context_depth} for node: {node_name}"
                )
                context = self._get_node_context(node_name, context_depth)
                logging.debug(f"Context gathered, length: {len(context)}")

            # Get node data for variable substitution
            node = self.node_operations.get_node_by_name(node_name)
            if not node:
                callback("", f"Could not find node: {node_name}")
                return

            # Strip HTML from the description for the node data
            node["description"] = description

            # Prepare variables
            variables = self._prompt_template_service.prepare_context_variables(
                node_data=node, context=context, custom_instructions=custom_instructions
            )

            # Format the template
            template = self._get_appropriate_template(template_id, focus_type)
            if not template:
                callback("", "No suitable template found")
                return

            prompt = template.format(variables)

            # Send to LLM API (using existing API call mechanism)
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": float(os.getenv("OPENAI_TEMPERATURE", 0.7)),
                "max_tokens": int(os.getenv("OPENAI_MAX_TOKENS", 1000)),
            }

            endpoint_url = self.base_url

            logging.debug(f"Making enhanced LLM request to: {endpoint_url}")
            logging.debug(f"Template used: {template.name}")
            logging.debug(f"Payload: {payload}")

            response = requests.post(
                endpoint_url, headers=headers, json=payload, timeout=60
            )

            response.raise_for_status()
            result = response.json()
            logging.debug(f"Enhanced LLM response: {result}")

            # Process response
            if "choices" in result and len(result["choices"]) > 0:
                completion = result["choices"][0]["message"]["content"]
            else:
                # Try alternative formats
                completion = result.get(
                    "response",
                    result.get("content", result.get("output", str(result))),
                )

            # Return enhanced text
            callback(completion, None)

        except Exception as e:
            logging.error(f"Error in enhanced LLM request: {e}")
            callback("", str(e))

    def _get_appropriate_template(self, template_id: str, focus_type: str):
        """Get the appropriate template, falling back as needed."""
        template = self._prompt_template_service.get_template(template_id)
        if not template:
            # Fall back to focus type if template not found
            template = self._prompt_template_service.get_template(focus_type)
            if not template:
                # Fall back to general template as last resort
                template = self._prompt_template_service.get_template("general")
        return template
