import json
import os
from base64 import urlsafe_b64encode
from typing import Dict, Optional, Any

from cryptography.fernet import Fernet

from rka.components.io.log_service import LogService
from rka.log_configs import LOG_COMMON

logger = LogService(LOG_COMMON)


class CredentialsManager:
    def __init__(self, root_path: str, uid: str):
        assert root_path
        assert uid
        self.__root_path = root_path
        self.__master_key = None
        self.__credentials: Optional[Dict[str, Dict[str, str]]] = None
        self.__internal_key = CredentialsManager.__str_to_key(uid)

    @staticmethod
    def __str_to_key(key_str: str):
        while len(key_str) < 32:
            key_str += key_str
        key_str = key_str[:32]
        key_bytes = key_str.encode()
        return urlsafe_b64encode(key_bytes)

    def __get_credentials_filename(self, extension: str) -> str:
        path = os.path.realpath(self.__root_path)
        return os.path.join(path, f'credentials.{extension}')

    def __read_plain_file(self, extension: str) -> Optional[str]:
        filename = self.__get_credentials_filename(extension)
        try:
            with open(filename, 'rt') as file:
                data = file.read()
        except IOError as e:
            print(e)
            return None
        return data

    def __write_plain_file(self, extension: str, data: str) -> bool:
        encoded_bytes = data.encode(encoding='utf-8')
        filename = self.__get_credentials_filename(extension)
        try:
            with open(filename, 'wb') as file:
                file.write(encoded_bytes)
        except IOError as e:
            print(e)
            return False
        return True

    def __read_encrypted_file(self, extension: str, key) -> Optional[str]:
        filename = self.__get_credentials_filename(extension)
        try:
            with open(filename, 'rb') as file:
                encrypted_bytes = file.read()
        except IOError as e:
            print(e)
            return None
        fernet = Fernet(key)
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        return str(decrypted_bytes, encoding='utf-8')

    def __write_encrypted_file(self, extension: str, key, data: str) -> bool:
        encoded_bytes = data.encode(encoding='utf-8')
        fernet = Fernet(key)
        encrypted_bytes = fernet.encrypt(encoded_bytes)
        filename = self.__get_credentials_filename(extension)
        try:
            with open(filename, 'wb') as file:
                file.write(encrypted_bytes)
        except IOError as e:
            print(e)
            return False
        return True

    def __read_master_password(self) -> bool:
        if self.__master_key is not None:
            return True
        decrypted_master_str = self.__read_encrypted_file('master', self.__internal_key)
        if not decrypted_master_str:
            return False
        self.__master_key = CredentialsManager.__str_to_key(decrypted_master_str)
        return True

    def open_credentials(self) -> bool:
        if self.__credentials is not None:
            return True
        if not self.__read_master_password():
            return False
        decrypted_creds = self.__read_encrypted_file('enc', self.__master_key)
        if not decrypted_creds:
            unencrypted_creds = self.__read_plain_file('json')
            if unencrypted_creds:
                unencrypted_creds_dict = json.loads(unencrypted_creds)
                for key, key_dict in unencrypted_creds_dict.items():
                    if not isinstance(key, str):
                        logger.warn(f'expected str key, got {key}')
                        return False
                    if not isinstance(key_dict, dict):
                        logger.warn(f'expected dict, got {key_dict}')
                        return False
                    for field_key in key_dict.keys():
                        if not isinstance(field_key, str):
                            logger.warn(f'expected str key, got {field_key}')
                            return False
                self.__write_encrypted_file('enc', self.__master_key, unencrypted_creds)
            decrypted_creds = self.__read_encrypted_file('enc', self.__master_key)
            if not decrypted_creds:
                return False
        self.__credentials = json.loads(decrypted_creds)
        return True

    def set_master_password(self, password: str, save_to_file: bool):
        self.__master_key = CredentialsManager.__str_to_key(password)
        if save_to_file:
            self.__write_encrypted_file('master', self.__internal_key, password)

    def get_credentials(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.open_credentials():
            logger.error(f'Could not open credentials at {self.__root_path}')
            return None
        if key not in self.__credentials:
            logger.warn(f'No key {key} in credentials')
            return None
        return dict(self.__credentials[key])

    def recover_plain_file(self) -> bool:
        if not self.open_credentials():
            logger.error(f'Could not open credentials at {self.__root_path}')
            return False
        unencrypted_creds = json.dumps(self.__credentials, indent=4)
        return self.__write_plain_file('json', unencrypted_creds)
