import re
from dataclasses import dataclass
from typing import Pattern


@dataclass
class ValidationRules:
    """Shared validation rules for Neo4j naming requirements."""

    # Maximum length for any name in Neo4j
    MAX_LENGTH: int = 65534

    # Regex patterns for name validation
    FIRST_CHAR_PATTERN: str = (
        r"^[a-zA-Z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]"
    )
    VALID_CHARS_PATTERN: str = (
        r"^[a-zA-Z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD][a-zA-Z0-9\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD_]*$"
    )

    # Compile patterns with Unicode flag
    first_char_check: Pattern = re.compile(FIRST_CHAR_PATTERN)
    valid_chars_check: Pattern = re.compile(VALID_CHARS_PATTERN)

    # Error messages
    EMPTY_NAME_ERROR: str = "Name cannot be empty"
    LENGTH_ERROR: str = "Name exceeds maximum length of {}"
    INVALID_START_ERROR: str = "Name must start with a letter"
    INVALID_CHARS_ERROR: str = "Name must contain only letters, numbers, or underscores"
