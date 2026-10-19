from datetime import timedelta
import pytest
from app.core.exceptions import AuthenticationError
from app.core.security import create_jwt_token, decode_jwt_token, hash_password, verify_password


def test_password_hashing():
    raw_pw = "SuperSecret123!"
    hashed = hash_password(raw_pw)

    assert hashed != raw_pw
    assert verify_password(raw_pw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_creation_and_decoding():
    user_id = "11111111-2222-3333-4444-555555555555"
    token = create_jwt_token(subject=user_id, claims={"role": "organizer"})

    payload = decode_jwt_token(token, expected_type="access")
    assert payload["sub"] == user_id
    assert payload["role"] == "organizer"
    assert payload["type"] == "access"


def test_jwt_invalid_token_type():
    user_id = "test-user-id"
    refresh_token = create_jwt_token(subject=user_id, token_type="refresh")

    with pytest.raises(AuthenticationError, match="Invalid token type"):
        decode_jwt_token(refresh_token, expected_type="access")


def test_jwt_expired_token():
    user_id = "test-user-id"
    # Create token expired 1 hour ago
    expired_token = create_jwt_token(
        subject=user_id,
        expires_delta=timedelta(seconds=-3600),
    )

    with pytest.raises(AuthenticationError, match="Token has expired"):
        decode_jwt_token(expired_token)
