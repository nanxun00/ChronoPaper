from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

from src.settings import get_settings

_settings = get_settings()
key = _settings.aes_key.encode('utf-8')
iv = _settings.aes_iv.encode('utf-8')


def encrypt(text):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_text = pad(text.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded_text)
    return base64.b64encode(encrypted).decode('utf-8')


def decrypt(encrypted_text):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decoded_data = base64.b64decode(encrypted_text)
    decrypted = unpad(cipher.decrypt(decoded_data), AES.block_size)
    return decrypted.decode('utf-8')


if __name__ == "__main__":
    text = "hello_world"
    encrypted_text = encrypt(text)
    decrypted_text = decrypt(encrypted_text)
    print(encrypted_text)
    print(decrypted_text)
