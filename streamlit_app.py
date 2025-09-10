import os
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

# Spotify OAuth Configuration
SCOPE = "playlist-read-private playlist-read-collaborative user-library-read"

def get_spotify_client():
    """Initialize and return an authenticated Spotify client."""
    try:
        # Try to get credentials from Streamlit secrets first, then environment variables
        client_id = st.secrets.get("SPOTIPY_CLIENT_ID") or os.getenv("SPOTIPY_CLIENT_ID")
        client_secret = st.secrets.get("SPOTIPY_CLIENT_SECRET") or os.getenv("SPOTIPY_CLIENT_SECRET")
        redirect_uri = st.secrets.get("SPOTIPY_REDIRECT_URI") or os.getenv("SPOTIPY_REDIRECT_URI")
        
        if not all([client_id, client_secret, redirect_uri]):
            st.error("Missing Spotify credentials")
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

def search_playlist(sp: spotipy.Spotify, playlist_id: str, filters: Dict) -> List[Dict]:
    """Search for tracks in a playlist based on filters."""
    results = []
    offset = 0
    while True:
        response = sp.playlist_items(playlist_id, offset=offset, fields='items.track(name,artists,album(name),id),next')
        
        # Filter tracks based on user criteria
        for item in response['items']:
            track = item['track']
            if track:  # Some tracks might be None due to availability
                matches_filters = True
                
                # Apply filters
                if filters.get('artist_filter') and not any(
                    filters['artist_filter'].lower() in artist['name'].lower() 
                    for artist in track['artists']
                ):
                    matches_filters = False
                
                if filters.get('album_filter') and filters['album_filter'].lower() not in track['album']['name'].lower():
                    matches_filters = False
                
                if filters.get('track_filter') and filters['track_filter'].lower() not in track['name'].lower():
                    matches_filters = False
                
                if matches_filters:
                    results.append(track)
        
        # Check if there are more items to fetch
        if not response.get('next'):
            break
        offset += len(response['items'])
    
    return results

# Main application logic
try:
    sp = get_spotify_client()

    if sp:
        # Add a refresh button
        if st.button("Refresh Playlists") or not st.session_state.playlists:
            st.session_state.playlists = []
            
            # Load playlists
            with st.spinner("Loading your playlists..."):
                st.session_state.playlists = load_playlists(sp)
                if not st.session_state.playlists:
                    st.warning("No playlists found. Please check your Spotify account.")
                    st.stop()
except Exception as e:
    st.error(f"Error in main application: {str(e)}")
    if "token_info" in st.session_state:
        st.session_state.token_info = None  # Clear token on error
    st.stop()
    # Playlist selection
    playlist_names = [playlist['name'] for playlist in st.session_state.playlists]
    selected_playlist_name = st.selectbox("Select a playlist", playlist_names)
    
    # Get selected playlist ID
    selected_playlist = next(
        (playlist for playlist in st.session_state.playlists if playlist['name'] == selected_playlist_name),
        None
    )
    
    if selected_playlist:
        st.session_state.selected_playlist = selected_playlist
        
        # Search filters
        st.subheader("Search Filters")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            artist_filter = st.text_input("Artist name contains:")
        with col2:
            album_filter = st.text_input("Album name contains:")
        with col3:
            track_filter = st.text_input("Track name contains:")
        
        # Search button
        if st.button("Search"):
            filters = {
                'artist_filter': artist_filter,
                'album_filter': album_filter,
                'track_filter': track_filter
            }
            
            with st.spinner("Searching playlist..."):
                st.session_state.search_results = search_playlist(sp, selected_playlist['id'], filters)
            
            # Display results
            if st.session_state.search_results:
                st.subheader(f"Found {len(st.session_state.search_results)} matches:")
                for track in st.session_state.search_results:
                    artists = ", ".join(artist['name'] for artist in track['artists'])
                    st.write(f"🎵 {track['name']} - {artists} ({track['album']['name']})")
            else:
                st.info("No matches found with the current filters.")
else:
    st.error("Please configure Spotify credentials to use this application.")
    st.markdown("""
    ### Setup Instructions:
    1. Create a Spotify Developer account at https://developer.spotify.com
    2. Create a new application in the Spotify Developer Dashboard
    3. Set the following environment variables:
        - SPOTIPY_CLIENT_ID
        - SPOTIPY_CLIENT_SECRET
        - SPOTIPY_REDIRECT_URI (e.g., http://localhost:8501)
    """)
