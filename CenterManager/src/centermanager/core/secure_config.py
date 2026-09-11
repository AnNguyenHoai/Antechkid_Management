import os
import json
import base64
from pathlib import Path
from typing import Any, Dict

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import getpass
import platform

from centermanager.core.paths import get_paths

class SecureConfig:
    def __init__(self):
        self.config_dir = get_paths().config_dir
        self.config_file = self.config_dir / "config_encrypted.json"
        self.key_file = self.config_dir / ".config_key"
        self._key = self._load_or_generate_key()
        self._data = self._load()

    def _load_or_generate_key(self) -> bytes:
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            # Derive key from machine+user (not perfect but better than nothing)
            salt = os.urandom(16)
            passphrase = platform.node() + getpass.getuser()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            key = kdf.derive(passphrase.encode())
            with open(self.key_file, 'wb') as f:
                f.write(key)
            return key

    def _load(self) -> Dict[str, Any]:
        if not self.config_file.exists():
            return {}
        with open(self.config_file, 'r') as f:
            data = json.load(f)
        if 'encrypted_data' in data and 'nonce' in data:
            encrypted = base64.b64decode(data['encrypted_data'])
            nonce = base64.b64decode(data['nonce'])
            aesgcm = AESGCM(self._key)
            try:
                decrypted = aesgcm.decrypt(nonce, encrypted, None)
                return json.loads(decrypted.decode('utf-8'))
            except Exception:
                return {}
        return {}

    def save(self, data: Dict[str, Any]):
        json_str = json.dumps(data, indent=2)
        aesgcm = AESGCM(self._key)
        nonce = os.urandom(12)
        encrypted = aesgcm.encrypt(nonce, json_str.encode(), None)
        store = {
            'nonce': base64.b64encode(nonce).decode(),
            'encrypted_data': base64.b64encode(encrypted).decode()
        }
        with open(self.config_file, 'w') as f:
            json.dump(store, f, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save(self._data)