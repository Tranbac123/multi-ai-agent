import hmac, hashlib, base64

def sign(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return "sha256="+base64.b64encode(mac).decode()

