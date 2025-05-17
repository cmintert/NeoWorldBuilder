import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List


class PromptTemplate:
    """Represents a template for LLM prompting."""

    def __init__(
        self,
        name: str,
        template: str,
        description: str = "",
        focus_type: str = "general",
    ):
        self.name = name
        self.template = template
        self.description = description
        self.focus_type = focus_type  # "general", "details", "style", "consistency"

    def format(self, variables: Dict[str, Any]) -> str:
        """Format the template by replacing variables with values."""
        result = self.template
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value))
        return result


class PromptTemplateService:
    """Service for managing LLM prompt templates."""

    def __init__(self) -> None:
        """Initialize with default templates."""
        self.logger = logging.getLogger(__name__)
        self.templates = self._initialize_default_templates()

    def _initialize_default_templates(self) -> Dict[str, PromptTemplate]:
        """Initialize default templates."""
        return {
            "general": PromptTemplate(
                name="General Enhancement",
                description="Improve the overall quality of the description",
                focus_type="general",
                template="""
You are helping to enhance a description for a world-building project.

Node Information:
- Name: {node_name}
- Type: {node_type}
- Labels: {labels}
- Tags: {tags}

Connected Nodes:
{context}

Current Description:
{description}

Please enhance this description by:
1. Adding more vivid details
2. Improving the writing style
3. Ensuring consistency with the connected nodes
4. Maintaining the original tone and factual information

Your task is to produce an improved version that maintains all existing information while making it more engaging and detailed.""",
            ),
            "details": PromptTemplate(
                name="Add Details",
                description="Expand the description with additional details",
                focus_type="details",
                template="""
You are helping to add more details to a description for a world-building project.

Node Information:
- Name: {node_name}
- Type: {node_type}
- Labels: {labels}
- Tags: {tags}

Connected Nodes:
{context}

Current Description:
{description}

Please enhance this description by adding more sensory details, background information, and specific characteristics. Focus on expanding the existing content rather than changing the style. Maintain the original tone and all factual information.""",
            ),
            "style": PromptTemplate(
                name="Improve Style",
                description="Refine the writing style while preserving content",
                focus_type="style",
                template="""
You are helping to improve the writing style of a description for a world-building project.

Node Information:
- Name: {node_name}
- Type: {node_type}
- Labels: {labels}
- Tags: {tags}

Connected Nodes:
{context}

Current Description:
{description}

Please improve the writing style of this description while maintaining all factual information. Focus on:
1. Making the prose more engaging
2. Improving flow and readability
3. Using more vivid language
4. Maintaining consistency with the original tone""",
            ),
        }

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a template by ID."""
        return self.templates.get(template_id)

    def get_all_templates(self) -> List[PromptTemplate]:
        """Get all available templates."""
        return list(self.templates.values())

    def format_template(
        self, template_id: str, variables: Dict[str, Any]
    ) -> Optional[str]:
        """Format a template with the given variables."""
        template = self.get_template(template_id)
        if not template:
            self.logger.error(f"Template not found: {template_id}")
            return None

        try:
            return template.format(variables)
        except Exception as e:
            self.logger.error(f"Error formatting template: {str(e)}")
            return None

    def prepare_context_variables(
        self, node_data: Dict[str, Any], context: str, custom_instructions: str = ""
    ) -> Dict[str, Any]:
        """Prepare variables for template substitution."""
        # Extract labels and determine node type
        labels = node_data.get("labels", [])
        node_type = "General"

        # Attempt to determine a more specific node type from labels
        type_mapping = {
            "CHARACTER": "Character",
            "LOCATION": "Location",
            "ITEM": "Item",
            "EVENT": "Event",
            "TIMELINE": "Timeline",
            "MAP": "Map",
            "FACTION": "Faction",
            "ORGANIZATION": "Organization",
        }

        for label in labels:
            if label.upper() in type_mapping:
                node_type = type_mapping[label.upper()]
                break

        # Build variables dictionary
        variables = {
            "node_name": node_data.get("name", ""),
            "node_type": node_type,
            "labels": ", ".join(labels),
            "tags": node_data.get("tags", ""),
            "description": node_data.get("description", ""),
            "context": context or "No connected nodes available",
            "custom_instructions": custom_instructions,
        }

        return variables
