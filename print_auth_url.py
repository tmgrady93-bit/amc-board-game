import os
import tomllib
import webbrowser
from spotipy.oauth2 import SpotifyOAuth

# Load secrets from .streamlit/secrets.toml if present, else environment
secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
secrets = {}
if os.path.exists(secrets_path):
    with open(secrets_path, 'rb') as f:
        secrets = tomllib.load(f)

CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID') or secrets.get('SPOTIPY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET') or secrets.get('SPOTIPY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI') or secrets.get('SPOTIPY_REDIRECT_URI')

if not (CLIENT_ID and CLIENT_SECRET and REDIRECT_URI):
    print('Missing SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET or SPOTIPY_REDIRECT_URI. Set them in environment or .streamlit/secrets.toml')
    raise SystemExit(1)

SCOPE = 'user-library-read user-read-playback-state user-modify-playback-state playlist-read-private'
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE, open_browser=False)
url = sp_oauth.get_authorize_url()
print('Authorize URL:')
print(url)

# Try to open in default browser
try:
    webbrowser.open(url)
    print('\nOpened the authorization URL in your default browser.')
except Exception as e:
    print(f'Could not open browser automatically: {e}')
    print('Please copy the URL above and open it manually.')
