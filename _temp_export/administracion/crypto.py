import base64
from cryptography.fernet import Fernet
from django.conf import settings

def get_cipher():
    key = settings.SECRET_KEY[:32].encode('utf-8')
    key = base64.urlsafe_b64encode(key.ljust(32, b'0'))
    return Fernet(key)

def encrypt(text):
    if not text: return text
    if text.startswith('gAAAAA'): return text # Already encrypted roughly
    return get_cipher().encrypt(text.encode('utf-8')).decode('utf-8')

def decrypt(text):
    if not text: return text
    try:
        return get_cipher().decrypt(text.encode('utf-8')).decode('utf-8')
    except Exception:
        return text # fallback if not encrypted
