from cryptography.fernet import Fernet

KEY_FILE = "secret.key"

def generate_key():
    """
    Generates a key and save it into a file
    """
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as key_file:
        key_file.write(key)

def load_key():
    """
    Load the previously generated key from the key file.
    Raises FileNotFoundError if the key file does not exist.
    """
    try:
        with open(KEY_FILE, "rb") as key_file:
            return key_file.read()
    except FileNotFoundError:
        print(f"ERROR: Encryption key file '{KEY_FILE}' not found. Please generate a key first.")
        raise

def encrypt_password(password):
    """
    Encrypts a password
    """
    key = load_key()
    encoded_password = password.encode()
    f = Fernet(key)
    encrypted_password = f.encrypt(encoded_password)
    return encrypted_password.decode()

def decrypt_password(encrypted_password):
    """
    Decrypts an encrypted password
    """
    key = load_key()
    f = Fernet(key)
    decrypted_password = f.decrypt(encrypted_password.encode())
    return decrypted_password.decode()
