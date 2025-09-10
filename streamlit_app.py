import os
import random
import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from typing import Dict, List

# Configure page
st.set_page_config(page_title="Spotify Playlist Search", layout="centered")
st.title("Spotify Playlist Search")

# Initialize session state
if "playlists" not in st.session_state:
    st.session_state.playlists = []
if "selected_playlist" not in st.session_state:
    st.session_state.selected_playlist = None
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "token_info" not in st.session_state:
    st.session_state.token_info = None
if "random_track" not in st.session_state:
    st.session_state.random_track = None
if "random_track_playlist_id" not in st.session_state:
    st.session_state.random_track_playlist_id = None

# Spotify OAuth Configuration
# Include playback scopes for optional device playback
SCOPE = "playlist-read-private playlist-read-collaborative user-library-read user-read-playback-state user-modify-playback-state"

def get_spotify_client():
    """Initialize and return an authenticated Spotify client."""
    try:
        # Try to get credentials from Streamlit secrets first, then environment variables
        client_id = (
            st.secrets["SPOTIPY_CLIENT_ID"] if "SPOTIPY_CLIENT_ID" in st.secrets else os.getenv("SPOTIPY_CLIENT_ID")
        )
        client_secret = (
            st.secrets["SPOTIPY_CLIENT_SECRET"] if "SPOTIPY_CLIENT_SECRET" in st.secrets else os.getenv("SPOTIPY_CLIENT_SECRET")
        )
        redirect_uri = (
            st.secrets["SPOTIPY_REDIRECT_URI"] if "SPOTIPY_REDIRECT_URI" in st.secrets else os.getenv("SPOTIPY_REDIRECT_URI")
        )
        
        if not all([client_id, client_secret, redirect_uri]):
            st.error("Missing Spotify credentials")
            st.info(
                "Set SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI in Streamlit Cloud (App → Settings → Secrets) or locally in .streamlit/secrets.toml."
            )
            return None

        sp_oauth = SpotifyOAuth(
            scope=SCOPE,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            open_browser=False,
            show_dialog=True
        )

        # If we don't have a token yet
        if not st.session_state.token_info:
            # Check URL parameters for auth code
            params = st.experimental_get_query_params()
            code = params.get("code", [None])[0]
            
            if code:
                try:
                    # Get token with the code
                    token_info = sp_oauth.get_access_token(code, check_cache=False)
                    st.session_state.token_info = token_info
                    # Clear the URL parameters
                    st.experimental_set_query_params()
                except Exception as e:
                    st.error(f"Error getting access token: {e}")
                    return None
            else:
                # No code in URL, show the auth URL
                auth_url = sp_oauth.get_authorize_url()
                st.markdown(f"Please click here to authenticate: [Authenticate with Spotify]({auth_url})")
                st.stop()
        
        # Check if token needs refresh
        if st.session_state.token_info:
            if sp_oauth.is_token_expired(st.session_state.token_info):
                try:
                    st.session_state.token_info = sp_oauth.refresh_access_token(st.session_state.token_info['refresh_token'])
                except Exception as e:
                    st.error(f"Error refreshing token: {e}")
                    st.session_state.token_info = None
                    return None

            # Create Spotify client with the token
            sp = spotipy.Spotify(auth=st.session_state.token_info['access_token'])
            try:
                # Test the connection
                sp.current_user()
                return sp
            except Exception as e:
                st.error(f"Error validating Spotify connection: {e}")
                st.session_state.token_info = None
                return None
        
        return None
        
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        st.info("Check your Spotify credentials in .streamlit/secrets.toml")
        return None

def load_playlists(sp: spotipy.Spotify) -> List[Dict]:
    """Load user's playlists."""
    try:
        st.write("Debug - Fetching playlists...")
        results = sp.current_user_playlists()
        playlists = []
        while results:
            st.write(f"Debug - Found {len(results['items'])} playlists in current batch")
            playlists.extend(results['items'])
            if results['next']:
                results = sp.next(results)
            else:
                break
        st.write(f"Debug - Total playlists loaded: {len(playlists)}")
        return playlists
    except Exception as e:
        st.error(f"Error loading playlists: {str(e)}")
        return []

def load_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> List[Dict]:
    """Load all tracks for a given playlist (returns list of track objects)."""
    tracks: List[Dict] = []
    try:
        fields = 'items.track(id,name,preview_url,external_urls.spotify,artists(name),album(name)),next'
        results = sp.playlist_items(playlist_id, fields=fields)
        while results:
            for item in results.get('items', []):
                track = item.get('track')
                if track:
                    tracks.append(track)
            if results.get('next'):
                results = sp.next(results)
            else:
                break
    except Exception as e:
        st.error(f"Error loading tracks: {e}")
    return tracks

def search_playlist(sp: spotipy.Spotify, playlist_id: str, filters: Dict) -> List[Dict]:
    """Search for tracks in a playlist based on filters."""
    results: List[Dict] = []
    offset = 0
    while True:
        response = sp.playlist_items(
            playlist_id,
            offset=offset,
            fields='items.track(name,artists,album(name),id,preview_url,external_urls.spotify),next',
        )

        for item in response.get('items', []):
            track = item.get('track')
            if not track:
                continue
            matches = True
            if filters.get('artist_filter') and not any(
                filters['artist_filter'].lower() in a['name'].lower() for a in track.get('artists', [])
            ):
                matches = False
            if matches and filters.get('album_filter') and (
                filters['album_filter'].lower() not in (track.get('album') or {}).get('name', '').lower()
            ):
                matches = False
            if matches and filters.get('track_filter') and (
                filters['track_filter'].lower() not in track.get('name', '').lower()
            ):
                matches = False
            if matches:
                results.append(track)

        if not response.get('next'):
            break
        offset += len(response.get('items', []))

    return results

# ========================
# Main application UI
# ========================
try:
    sp = get_spotify_client()
except Exception as e:
    st.error(f"Error in authentication: {e}")
    if "token_info" in st.session_state:
        st.session_state.token_info = None
    st.stop()

if not sp:
    st.stop()

# Load playlists (first time or when refreshed)
if st.button("Refresh Playlists") or not st.session_state.playlists:
    st.session_state.playlists = []
    with st.spinner("Loading your playlists..."):
        st.session_state.playlists = load_playlists(sp)
        if not st.session_state.playlists:
            st.warning("No playlists found. Please check your Spotify account.")
            st.stop()

# Playlist selection UI
playlist_names = [p['name'] for p in st.session_state.playlists]
selected_playlist_name = st.selectbox("Select a playlist", playlist_names)
selected_playlist = next((p for p in st.session_state.playlists if p['name'] == selected_playlist_name), None)

if not selected_playlist:
    st.stop()

st.session_state.selected_playlist = selected_playlist

with st.expander("Search Filters (optional)"):
    col1, col2, col3 = st.columns(3)
    with col1:
        artist_filter = st.text_input("Artist contains")
    with col2:
        album_filter = st.text_input("Album contains")
    with col3:
        track_filter = st.text_input("Track contains")

    if st.button("Search"):
        with st.spinner("Searching playlist..."):
            st.session_state.search_results = search_playlist(
                sp,
                selected_playlist['id'],
                {
                    'artist_filter': artist_filter,
                    'album_filter': album_filter,
                    'track_filter': track_filter,
                },
            )
        if st.session_state.search_results:
            st.subheader(f"Found {len(st.session_state.search_results)} matches:")
            for track in st.session_state.search_results:
                artists = ", ".join(artist['name'] for artist in track['artists'])
                st.write(f"\ud83c\udfb5 {track['name']} - {artists} ({track['album']['name']})")
        else:
            st.info("No matches found with the current filters.")

st.subheader("Feeling lucky?")
if st.button("Roll the dice 🎲"):
    with st.spinner("Rolling and fetching tracks..."):
        tracks = load_playlist_tracks(sp, selected_playlist['id'])
    valid_tracks = [t for t in tracks if t]
    if not valid_tracks:
        st.warning("No tracks found in this playlist.")
    else:
        choice = random.choice(valid_tracks)
        artists = ", ".join(artist['name'] for artist in choice.get('artists', []))
        st.session_state.random_track = choice
        st.session_state.random_track_playlist_id = selected_playlist['id']
        st.success(f"Selected: {choice.get('name')} — {artists} ({choice.get('album', {}).get('name', '')})")
        st.caption("Click the Play button below to hear a 30-second preview (when available).")

# Clear stored random track if user switched playlists
if st.session_state.random_track_playlist_id and st.session_state.random_track_playlist_id != selected_playlist['id']:
    st.session_state.random_track = None
    st.session_state.random_track_playlist_id = selected_playlist['id']

# Show Play button for the selected random track
if st.session_state.random_track:
    track = st.session_state.random_track
    preview_url = track.get('preview_url')
    if preview_url:
        if st.button("▶ Play 30s preview", key="play_preview"):
            st.audio(preview_url)
    else:
        st.warning("This track has no 30-second preview available.")
        external_url = (track.get('external_urls') or {}).get('spotify')
        if external_url:
            st.markdown(f"Open in Spotify: [{external_url}]({external_url})")
