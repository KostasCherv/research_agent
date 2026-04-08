import asyncio
from unittest.mock import MagicMock, patch

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.auth import get_authenticated_user


def test_get_authenticated_user_rejects_missing_token():
    try:
        asyncio.run(get_authenticated_user(None))
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("Expected HTTPException for missing token")


def test_get_authenticated_user_accepts_valid_jwt_payload():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    mock_key = MagicMock()
    mock_key.key = "public-key"

    with (
        patch("src.auth.jwt.PyJWKClient") as mock_jwk_client_cls,
        patch("src.auth.jwt.decode") as mock_decode,
    ):
        mock_jwk_client = MagicMock()
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_key
        mock_jwk_client_cls.return_value = mock_jwk_client
        mock_decode.return_value = {"sub": "user-1", "email": "user@example.com"}

        user = asyncio.run(get_authenticated_user(credentials))

    assert user.user_id == "user-1"
    assert user.email == "user@example.com"


def test_get_authenticated_user_rejects_invalid_jwt():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")
    with patch("src.auth.jwt.PyJWKClient") as mock_jwk_client_cls:
        mock_jwk_client = MagicMock()
        mock_jwk_client.get_signing_key_from_jwt.side_effect = jwt.InvalidTokenError("invalid")
        mock_jwk_client_cls.return_value = mock_jwk_client

        try:
            asyncio.run(get_authenticated_user(credentials))
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("Expected HTTPException for invalid token")
