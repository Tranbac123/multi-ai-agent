from apps.data-plane.event-relay-service.src.crypto import sign  # type: ignore

def test_sign():
    secret = "test-secret"
    body = b"test-payload"
    signature = sign(secret, body)
    assert signature.startswith("sha256=")
    assert len(signature) > 10

