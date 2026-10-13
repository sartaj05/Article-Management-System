import base64
import hashlib
import hmac
import struct
import time


def generate_secret():
    import secrets
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def totp(secret, timestamp=None):
    timestamp = int(timestamp or time.time()) // 30
    key = base64.b32decode(secret + '=' * ((8 - len(secret) % 8) % 8), casefold=True)
    digest = hmac.new(key, struct.pack('>Q', timestamp), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return str((struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff) % 1000000).zfill(6)


def verify_totp(secret, code):
    code = str(code).strip()
    return any(hmac.compare_digest(totp(secret, time.time() + offset), code) for offset in (-30, 0, 30))
