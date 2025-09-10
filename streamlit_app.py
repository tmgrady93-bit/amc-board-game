import os
import streamlit as st
from urllib.parse import urlparse, parse_qs

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except Exception:
    spotipy = None


SCOPE = "user-library-read user-modify-playback-state user-read-playback-state playlist-read-private"

st.set_page_config(page_title="Mobile Spotify Selector", layout="centered")
st.title("Mobile Spotify Song Selector")

st.markdown("Enter selection values below to find a song from your Spotify collection and play it on an active device.")

# Helper: check env
CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID") or (st.secrets.get("SPOTIPY_CLIENT_ID") if hasattr(st, "secrets") else None)
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET") or (st.secrets.get("SPOTIPY_CLIENT_SECRET") if hasattr(st, "secrets") else None)
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI") or (st.secrets.get("SPOTIPY_REDIRECT_URI") if hasattr(st, "secrets") else None)

if not spotipy:
    st.error("Missing dependency: spotipy. Install from requirements.txt and restart the app.")
    st.stop()

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.warning("Set SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET and SPOTIPY_REDIRECT_URI before using the app. On Streamlit Cloud, add these values under 'Secrets' for your app; locally you can use environment variables (see README).")

# Create OAuth helper
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE, open_browser=False)

if "token_info" not in st.session_state:
    st.session_state.token_info = None

# Authorization flow (manual-friendly for mobile)
if not st.session_state.token_info:
    auth_url = sp_oauth.get_authorize_url()
    st.markdown("### Step 1 — Authorize")
    st.markdown(f"[Open Spotify authorization page]({auth_url})")
    st.info("On mobile: follow the link, login/authorize, then you'll be redirected to your REDIRECT_URI with a code. Copy the full redirected URL and paste it below.")
    redirect_response = st.text_input("Paste the full redirect URL after authorizing (leave empty if already done)")
    if redirect_response:
        # extract code
        try:
            code = parse_qs(urlparse(redirect_response).query).get("code", [None])[0]
            if not code:
                st.error("Couldn't find 'code' in the URL. Make sure you pasted the full redirect URL.")
            else:
                try:
                    token_info = sp_oauth.get_access_token(code)
                except TypeError:
                    # some spotipy versions return dict directly
                    token_info = sp_oauth.get_access_token(code)
                st.session_state.token_info = token_info
                st.experimental_rerun()
        except Exception as e:
            st.error(f"Error obtaining token: {e}")
    else:
        st.stop()

# token present
token_info = st.session_state.token_info
if not token_info:
    st.stop()

# Handle refresh if expired
if sp_oauth.is_token_expired(token_info):
    try:
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"]) if isinstance(token_info, dict) else sp_oauth.refresh_access_token(token_info.refresh_token)
        st.session_state.token_info = token_info
    except Exception:
        st.warning("Could not refresh token, please re-authorize.")
        st.session_state.token_info = None
        st.experimental_rerun()

access_token = token_info["access_token"] if isinstance(token_info, dict) else token_info['access_token']
sp = spotipy.Spotify(auth=access_token)

st.markdown("---")

# Selection inputs
st.markdown("### Select criteria")
col1, col2 = st.columns(2)
with col1:
    mood = st.selectbox("Mood", ["Happy", "Neutral", "Sad"], index=1)
    energy = st.slider("Energy (0=calm, 1=energetic)", 0.0, 1.0, 0.5, 0.01)
    tempo = st.slider("Tempo target (BPM)", 60, 180, 100)
with col2:
    genres = st.multiselect("Seed genres (optional)", [
        "pop", "rock", "hip-hop", "electronic", "classical", "jazz", "blues", "country", "reggae", "metal",
    ])
    artist_name = st.text_input("Artist name (optional)")

# map mood to valence
valence_map = {"Happy": 0.8, "Neutral": 0.5, "Sad": 0.2}
valence = valence_map.get(mood, 0.5)

if st.button("Find songs"):
    # get seed artists if provided
    seed_artists = []
    if artist_name:
        try:
            res = sp.search(q=f"artist:{artist_name}", type="artist", limit=1)
            items = res.get("artists", {}).get("items", [])
            if items:
                seed_artists = [items[0]["id"]]
        except Exception as e:
            st.warning(f"Error searching artist: {e}")

    # prepare recommendation parameters
    rec_kwargs = {
        "limit": 20,
        "target_valence": float(valence),
        "target_energy": float(energy),
        "target_tempo": int(tempo),
    }
    if genres:
        # Spotify requires at least 1 seed (max 5) - use genres as seeds if present
        rec_kwargs["seed_genres"] = genres[:5]
    elif seed_artists:
        rec_kwargs["seed_artists"] = seed_artists[:5]
    else:
        # fallback seed genres
        rec_kwargs["seed_genres"] = ["pop"]

    try:
        recs = sp.recommendations(**rec_kwargs)
        tracks = recs.get("tracks", [])
    except Exception as e:
        st.error(f"Error getting recommendations: {e}")
        tracks = []

    if not tracks:
        st.info("No tracks found with these criteria. Try different seeds or loosen constraints.")
    else:
        options = [f"{t['name']} — {t['artists'][0]['name']}" for t in tracks]
        idx = st.radio("Choose a song", range(len(options)), format_func=lambda i: options[i])
        chosen = tracks[idx]
        st.markdown(f"**Selected:** {options[idx]}")

        if st.button("Play on my active device"):
            try:
                uri = chosen["uri"]
                sp.start_playback(uris=[uri])
                st.success("Playback started (if you have an active Spotify device).")
            except spotipy.SpotifyException as e:
                st.error(f"Spotify API error: {e}. Make sure you have an active device (Spotify app open on a device) and granted playback scope.")
            except Exception as e:
                st.error(f"Error starting playback: {e}")

# Extra: show user's playlists
st.markdown("---")
if st.checkbox("Show my playlists"):
    try:
        pls = sp.current_user_playlists(limit=50)
        for p in pls.get("items", []):
            st.write(f"{p['name']} — {p['tracks']['total']} tracks")
    except Exception as e:
        st.warning(f"Could not fetch playlists: {e}")



# Footer
st.markdown("---")
st.caption("This app uses the Spotify Web API. It requires a Spotify Premium account to control playback on devices.")
