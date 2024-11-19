from typing import Union

from cryptography.fernet import Fernet, InvalidToken


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
