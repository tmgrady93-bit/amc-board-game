import os
import time
import random
from typing import Dict, List

import spotipy
import streamlit as st
from spotipy.oauth2 import SpotifyOAuth

# Page config
st.set_page_config(page_title="AMC Board Game", layout="centered")
st.title("AMC Board Game")

st.markdown(
    """
    Welcome! This app powers music selection for the AMC board game. As players move around the board, roll a die,
    draw a color, and play a hidden song preview from that color’s playlist. Guess first, then reveal!
    """
)

# Global constants
COLORS = ["Red", "Orange", "Yellow", "Blue", "Purple"]
SCOPE = "playlist-read-private playlist-read-collaborative user-library-read user-read-playback-state user-modify-playback-state"

# Session state defaults
ss = st.session_state
ss.setdefault("page", "About")
ss.setdefault("token_info", None)
ss.setdefault("all_playlists", [])  # full objects from Spotify
ss.setdefault("color_playlists", {})  # {color: playlist_id}
ss.setdefault("tracks_cache", {})  # {color: [track_objs]}
ss.setdefault("teams_count", 2)
ss.setdefault("players_per_team", 2)
ss.setdefault("player_order", [])
ss.setdefault("current_player_index", 0)
ss.setdefault("last_roll", None)
ss.setdefault("current_color", None)
ss.setdefault("current_track", None)
ss.setdefault("reveal_answer", False)
ss.setdefault("timer_running", False)
ss.setdefault("timer_started_at", None)
ss.setdefault("elapsed_last_round", None)

# ---------- Spotify Auth ----------

def get_spotify_client() -> spotipy.Spotify | None:
    try:
        client_id = st.secrets["SPOTIPY_CLIENT_ID"] if "SPOTIPY_CLIENT_ID" in st.secrets else os.getenv("SPOTIPY_CLIENT_ID")
        client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"] if "SPOTIPY_CLIENT_SECRET" in st.secrets else os.getenv("SPOTIPY_CLIENT_SECRET")
        redirect_uri = st.secrets["SPOTIPY_REDIRECT_URI"] if "SPOTIPY_REDIRECT_URI" in st.secrets else os.getenv("SPOTIPY_REDIRECT_URI")

        if not all([client_id, client_secret, redirect_uri]):
            st.error("Missing Spotify credentials")
            st.info("Set SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI in Streamlit Cloud or .streamlit/secrets.toml")
            return None

        sp_oauth = SpotifyOAuth(
            scope=SCOPE,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            open_browser=False,
            show_dialog=True,
        )

        if not ss.token_info:
            qp = st.query_params
            code_val = qp.get("code") if "code" in qp else None
            code = code_val[0] if isinstance(code_val, list) and code_val else code_val
            if code:
                try:
                    ss.token_info = sp_oauth.get_access_token(code, check_cache=False)
                    try:
                        st.query_params.clear()
                    except Exception:
                        pass
                except Exception as e:
                    st.error(f"Error getting access token: {e}")
                    return None
            else:
                auth_url = sp_oauth.get_authorize_url()
                st.markdown(f"Please click here to authenticate: [Authenticate with Spotify]({auth_url})")
                st.stop()

        if ss.token_info and sp_oauth.is_token_expired(ss.token_info):
            try:
                ss.token_info = sp_oauth.refresh_access_token(ss.token_info["refresh_token"])
            except Exception as e:
                st.error(f"Error refreshing token: {e}")
                ss.token_info = None
                return None

        sp = spotipy.Spotify(auth=ss.token_info["access_token"]) if ss.token_info else None
        if sp:
            try:
                sp.current_user()
                return sp
            except Exception as e:
                st.error(f"Error validating Spotify connection: {e}")
                ss.token_info = None
                return None
        return None
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        return None

# ---------- Spotify helpers ----------

def load_playlists(sp: spotipy.Spotify) -> List[dict]:
    try:
        results = sp.current_user_playlists()
        playlists: List[dict] = []
        while results:
            playlists.extend(results.get("items", []))
            if results.get("next"):
                results = sp.next(results)
            else:
                break
        return playlists
    except Exception as e:
        st.error(f"Error loading playlists: {str(e)}")
        return []

def load_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> List[dict]:
    tracks: List[dict] = []
    try:
        fields = "items.track(id,name,preview_url,external_urls.spotify,artists(name),album(name)),next"
        results = sp.playlist_items(playlist_id, fields=fields)
        while results:
            for item in results.get("items", []):
                track = item.get("track")
                if track:
                    tracks.append(track)
            if results.get("next"):
                results = sp.next(results)
            else:
                break
    except Exception as e:
        st.error(f"Error loading tracks: {e}")
    return tracks

# ---------- UI helpers ----------

def ensure_spotify() -> spotipy.Spotify:
    sp = get_spotify_client()
    if not sp:
        st.stop()
    return sp

def sidebar_nav():
    st.sidebar.header("Navigation")
    ss.page = st.sidebar.radio("Go to", ["About", "Setup", "Game Play"], index=["About", "Setup", "Game Play"].index(ss.page))

def build_player_order(teams: int, players_per_team: int) -> list:
    return [f"Team {t} - Player {p}" for t in range(1, teams + 1) for p in range(1, players_per_team + 1)]

# ---------- Pages ----------

def render_about():
    st.subheader("About")
    st.markdown(
        """
        This game uses Spotify to supply songs while you play the AMC board game.

        1) Setup: choose teams and players, then assign a Spotify playlist to each color (Red, Orange, Yellow, Blue, Purple).
        2) Game Play: roll a die, the app picks a random color, and it plays a hidden song preview from that color’s playlist.
        3) Guess first, then reveal the answer and move to the next player.
        """
    )


def render_setup(sp: spotipy.Spotify):
    st.subheader("Setup")
    colA, colB = st.columns(2)
    with colA:
        ss.teams_count = st.number_input("Number of teams", min_value=1, max_value=8, value=ss.teams_count, step=1)
    with colB:
        ss.players_per_team = st.number_input("Players per team", min_value=1, max_value=10, value=ss.players_per_team, step=1)

    if st.button("Refresh Spotify Playlists") or not ss.all_playlists:
        with st.spinner("Loading your playlists..."):
            ss.all_playlists = load_playlists(sp)
            if not ss.all_playlists:
                st.warning("No playlists found.")

    playlist_names = [p['name'] for p in ss.all_playlists]
    name_to_id = {p['name']: p['id'] for p in ss.all_playlists}

    st.markdown("Assign a playlist to each color:")
    selects: Dict[str, str] = {}
    for color in COLORS:
        default_name = None
        assigned_id = ss.color_playlists.get(color)
        if assigned_id:
            for p in ss.all_playlists:
                if p['id'] == assigned_id:
                    default_name = p['name']
                    break
        options = ["-- None --"] + playlist_names
        index = 0
        if default_name and default_name in playlist_names:
            index = options.index(default_name)
        selects[color] = st.selectbox(f"{color} playlist", options=options, index=index)

    if st.button("Save Setup"):
        ss.color_playlists = {}
        ss.tracks_cache = {}
        for color, sel_name in selects.items():
            if sel_name and sel_name != "-- None --":
                pid = name_to_id.get(sel_name)
                if pid:
                    ss.color_playlists[color] = pid
        ss.player_order = build_player_order(ss.teams_count, ss.players_per_team)
        ss.current_player_index = 0
        with st.spinner("Preloading tracks for selected colors..."):
            for color, pid in ss.color_playlists.items():
                ss.tracks_cache[color] = load_playlist_tracks(sp, pid)
        st.success("Setup saved. You can proceed to Game Play.")

    st.divider()
    if st.button("Next ➡ Go to Game Play"):
        ss.page = "Game Play"


def draw_color_with_tracks() -> str | None:
    available = [c for c in COLORS if ss.tracks_cache.get(c)]
    return random.choice(available) if available else None


def start_round():
    ss.last_roll = random.randint(1, 6)
    ss.current_color = draw_color_with_tracks()
    ss.current_track = None
    ss.reveal_answer = False
    ss.timer_running = False
    ss.timer_started_at = None
    ss.elapsed_last_round = None

    if not ss.current_color:
        st.warning("No colors with assigned playlists. Please complete Setup.")
        return

    tracks = ss.tracks_cache.get(ss.current_color, [])
    if not tracks:
        st.warning(f"No tracks found for {ss.current_color}.")
        return

    ss.current_track = random.choice(tracks)


def render_timer_and_controls():
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Play", key="play_btn"):
            ss.timer_running = True
            ss.timer_started_at = time.time()
    with col2:
        if st.button("Pause", key="pause_btn") and ss.timer_running and ss.timer_started_at:
            ss.timer_running = False
            ss.elapsed_last_round = time.time() - ss.timer_started_at
    with col3:
        if st.button("Show Answer", key="reveal_btn"):
            ss.reveal_answer = True

    track = ss.current_track
    if track:
        preview_url = track.get('preview_url')
        if preview_url:
            st.audio(preview_url)
        else:
            st.info("No 30-second preview is available for this track.")

    if ss.timer_running and ss.timer_started_at:
        elapsed = time.time() - ss.timer_started_at
        st.caption(f"Timer running: {elapsed:.1f}s")
    elif ss.elapsed_last_round is not None:
        st.caption(f"Last round time: {ss.elapsed_last_round:.1f}s")


def render_game():
    st.subheader("Game Play")
    if not ss.player_order or not ss.color_playlists:
        st.warning("Please complete Setup first.")
        return

    current_player = ss.player_order[ss.current_player_index]
    st.markdown(f"**Current player:** {current_player}")

    if st.button("Roll Dice 🎲"):
        start_round()

    if ss.last_roll:
        st.write(f"Roll result: {ss.last_roll}")
        if ss.current_color:
            st.write(f"Color drawn: {ss.current_color}")
        else:
            st.warning("No valid color available. Assign playlists in Setup.")

    track = ss.current_track
    if track:
        if ss.reveal_answer:
            artists = ", ".join(a['name'] for a in track.get('artists', []))
            st.success(f"Answer: {track.get('name')} — {artists}")
        else:
            st.info("Track selected. Click Play to listen, then Reveal when ready.")
        render_timer_and_controls()

    st.divider()
    if st.button("Next ▶ Next Player"):
        total = len(ss.player_order)
        ss.current_player_index = (ss.current_player_index + 1) % total
        ss.last_roll = None
        ss.current_color = None
        ss.current_track = None
        ss.reveal_answer = False
        ss.timer_running = False
        ss.timer_started_at = None
        ss.elapsed_last_round = None


# ---- App entry ----
sp = ensure_spotify()
sidebar_nav()

if ss.page == "About":
    render_about()
elif ss.page == "Setup":
    if not ss.all_playlists:
        ss.all_playlists = load_playlists(sp)
    render_setup(sp)
else:
    if not ss.tracks_cache and ss.color_playlists:
        with st.spinner("Caching tracks..."):
            for color, pid in ss.color_playlists.items():
                ss.tracks_cache[color] = load_playlist_tracks(sp, pid)
    render_game()
