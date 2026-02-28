import authlib.integrations.starlette_client as starlette_client
import jwt as pyjwt  # PyJWT (our app tokens)
import time
from config import settings

def get_apple_client_secret():
    apple_client_secret = pyjwt.encode(
        {
            "iss": settings.APPLE_TEAM_ID,
            "iat": int(time.time()),
            "exp": int(time.time()) + 86400*180,
            "aud": "https://appleid.apple.com",
            "sub": settings.APPLE_CLIENT_ID
        },
        settings.APPLE_PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": settings.APPLE_KEY_ID}
    )

    return apple_client_secret


def get_oauth_apple_client():
    oauth_apple_client = starlette_client.OAuth()
    oauth_apple_client.register(
        name="apple",
        client_id=settings.APPLE_CLIENT_ID,
        client_secret=settings.APPLE_PRIVATE_KEY,
        authorize_url="https://appleid.apple.com/auth/authorize",
        access_token_url="https://appleid.apple.com/auth/token",
        api_base_url="https://appleid.apple.com",
        server_metadata_url="https://appleid.apple.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "name email",
            "response_mode": "form_post",
            "response_type": "code",
        },
    )

    return oauth_apple_client


client_secret = get_apple_client_secret()
oauth_apple= get_oauth_apple_client()