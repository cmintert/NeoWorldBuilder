import yaml
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
        id: str = "",
    ):
        self.name = name
        self.template = template
        self.description = description
        self.focus_type = focus_type  # "general", "details", "style", "consistency"
        self.id = id

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
        """Initialize templates from JSON file."""
        templates = {}
        templates_path = (
            Path(__file__).parent.parent / "config"
        )  # Or use a config setting
        template_file = templates_path / "prompt_templates.yaml"

        # Check if template file exists
        if not template_file.exists():
            self.logger.warning(
                f"Template file not found at {template_file}. No templates loaded."
            )
            self.logger.info("Please create a template file to use prompt templates.")
            return templates

        try:
            with open(template_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            for template_data in data.get("templates", []):
                template_id = template_data.get("id")
                if template_id:
                    templates[template_id] = PromptTemplate(
                        name=template_data.get("name", template_id),
                        description=template_data.get("description", ""),
                        focus_type=template_data.get("focus_type", "general"),
                        template=template_data.get("template", ""),
                        id=template_id,
                    )

            self.logger.info(f"Loaded {len(templates)} templates from {template_file}")
            return templates

        except Exception as e:
            self.logger.error(f"Error loading templates: {str(e)}")
            return templates  # Return empty dict if there's an error

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
        # Extract labels
        labels = node_data.get("labels", [])

        # For tags, ensure we have a list
        tags = node_data.get("tags", [])
        if isinstance(tags, str):
            tags = tags.split(",")

        # Build variables dictionary
        variables = {
            "node_name": node_data.get("name", ""),
            "labels": ", ".join(labels) if isinstance(labels, list) else labels,
            "tags": ", ".join(tags) if isinstance(tags, list) else tags,
            "description": node_data.get("description", ""),
            "context": context or "No connected nodes available",
            "custom_instructions": custom_instructions,
        }
        logging.debug(f"Prepared variables for template: {variables}")
        return variables
