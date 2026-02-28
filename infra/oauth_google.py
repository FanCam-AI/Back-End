import authlib.integrations.starlette_client as starlette_client
from config import settings


def get_oauth_google_client():
    oauth_google = starlette_client.OAuth()
    oauth_google.register(
        name='google',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

    return oauth_google

oauth_google = get_oauth_google_client()