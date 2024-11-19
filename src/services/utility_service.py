import re
from typing import List, Optional, Union
from PyQt6.QtWidgets import QTableWidgetItem
from cryptography.fernet import Fernet, InvalidToken


class UtilityService:
    """
    Service class to handle utility methods.
    """

    def __init__(self, config):
        """
        Initialize the UtilityService with the configuration.

        Args:
            config (Config): The configuration instance.
        """
        self.config = config

    def parse_comma_separated(self, text: str) -> List[str]:
        """
        Parse comma-separated input.

        Args:
            text (str): The comma-separated input text.

        Returns:
            list: The parsed list of strings.
        """
        return [item.strip() for item in text.split(",") if item.strip()]

    def validate_node_name(self, name: str) -> bool:
        """
        Validate node name.

        Args:
            name (str): The node name to validate.

        Returns:
            bool: True if the node name is valid, False otherwise.
        """
        return bool(re.match(r"^[a-zA-Z0-9_]+$", name))

    def add_or_update_property(self, table, key, value):
        found = False
        for row in range(table.rowCount()):
            item_key = table.item(row, 0)
            if item_key and item_key.text() == key:
                table.item(row, 1).setText(str(value))
                found = True
                break
        if not found:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(key))
            table.setItem(row, 1, QTableWidgetItem(str(value)))
            delete_button = self.create_delete_button(table, row)
            table.setCellWidget(row, 2, delete_button)

    def create_delete_button(self, table, row):
        # Placeholder for creating a delete button
        pass


class SecurityUtility:
    def __init__(self, key: Union[str, bytes]):
        """
        Initialize the SecurityUtility with a Fernet key.

        Args:
            key (Union[str, bytes]): The encryption key, either as a string or bytes.

        Raises:
            ValueError: If the key is neither a valid string nor bytes.
        """
        if isinstance(key, str):
            key = key.encode()
        elif not isinstance(key, bytes):
            raise ValueError("Key must be a string or bytes.")
        try:
            self.cipher = Fernet(key)
        except ValueError as e:
            raise ValueError(f"Invalid Fernet key: {str(e)}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using the Fernet cipher.

        Args:
            plaintext (str): The plaintext to encrypt.

        Returns:
            str: The encrypted text.

        Raises:
            ValueError: If plaintext is not a valid string.
            Exception: For any other unexpected errors during encryption.
        """
        if not isinstance(plaintext, str):
            raise ValueError("Plaintext must be a string.")
        try:
            return self.cipher.encrypt(plaintext.encode()).decode()
        except Exception as e:
            raise Exception(f"Failed to encrypt plaintext: {str(e)}")

    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt encrypted text using the Fernet cipher.

        Args:
            encrypted_text (str): The encrypted text to decrypt.

        Returns:
            str: The decrypted plaintext.

        Raises:
            ValueError: If encrypted_text is not a valid string.
            InvalidToken: If the token is invalid or tampered with.
            Exception: For any other unexpected errors during decryption.
        """
        if not isinstance(encrypted_text, str):
            raise ValueError("Encrypted text must be a string.")
        try:
            return self.cipher.decrypt(encrypted_text.encode()).decode()
        except InvalidToken:
            raise InvalidToken(
                "The encrypted text is invalid or has been tampered with."
            )
        except Exception as e:
            raise Exception(f"Failed to decrypt text: {str(e)}")

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            str: The generated key as a string.

        Raises:
            Exception: For any unexpected errors during key generation.
        """
        try:
            return Fernet.generate_key().decode()
        except Exception as e:
            raise Exception(f"Failed to generate encryption key: {str(e)}")
