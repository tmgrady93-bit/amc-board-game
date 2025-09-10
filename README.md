Mobile Spotify Song Selector (Streamlit)

Overview

This Streamlit app helps you pick and play a song from Spotify by entering selection values (mood, energy, genre, tempo). It's designed to work on mobile: after authorizing the app with Spotify, paste the redirect URL back into the app.

Prerequisites

- Python 3.8+
- Spotify developer app (client id / secret) registered at https://developer.spotify.com/dashboard/
- A Spotify Premium account to control playback on a device

Setup

1. Install dependencies (from the workspace root):

```cmd
python -m pip install -r requirements.txt
```

2. Set environment variables (replace placeholders):

```cmd
set SPOTIPY_CLIENT_ID=your_client_id
set SPOTIPY_CLIENT_SECRET=your_client_secret
set SPOTIPY_REDIRECT_URI=https://example.com/callback
```

The redirect URI must match one registered in your Spotify app settings. Because this app uses a manual paste flow, any reachable redirect URI (including localhost or a static page) will work.

Run the app

```cmd
streamlit run streamlit_app.py
```

On mobile, open the Streamlit URL provided by Streamlit, follow the authorization link inside the app, paste the redirect URL, then choose criteria and tap Play.

Notes & Troubleshooting

- Playback control requires an active Spotify device (open Spotify on your phone/desktop and start playback once).
- If you get permission errors, ensure your Spotify app has the required scopes: user-library-read, user-read-playback-state, user-modify-playback-state, playlist-read-private.
- If you prefer automatic OAuth redirection, consider deploying the app to a host with a publicly reachable redirect URI and set that URI in the Spotify dashboard.

Expose to the internet (public URL)

You have several options to give people a global URL to access this Streamlit app. Pick the approach that matches how long the app will be available and whether you want a managed host.

1) Quick, temporary: ngrok (best for quick demos)

- Download ngrok from https://ngrok.com/ and sign up for a free account.
- Authenticate ngrok with your token (one-time):

```cmd
ngrok authtoken <your-ngrok-auth-token>
```

- Run Streamlit locally (same project folder):

```cmd
C:\GameDevelopment\BasicGameDev\App_Deployment\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

- In a new shell, forward the local port (default Streamlit port is 8501):

```cmd
ngrok http 8501
```

Ngrok will print a public URL (https://...) which you can share. Note this is temporary and expires when ngrok stops.

2) Host on Streamlit Cloud (recommended for Streamlit-first apps)

- Push the repository to GitHub and sign into https://share.streamlit.io/ with the same GitHub account.
- Create a new app from your repo and branch; Streamlit Cloud will use `requirements.txt` and run the app. It provides a stable public URL.

3) Deploy to a general host (Render, Railway, Heroku, etc.)

- These providers accept a Git repo and run your app. Use the Procfile included in this repo which runs Streamlit on the platform port.
- Example Procfile (already added to repo):

```
web: streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
```

- Make sure `requirements.txt` lists `streamlit` and `spotipy` (it does). Configure the required environment variables (SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI) in the host's environment/secrets UI.

Security & notes
- Redirect URI in your Spotify developer settings must exactly match the redirect URI the deployed app uses (for Streamlit Cloud or a custom domain). For ngrok you can use the forwarded HTTPS URL as the redirect URI while testing (register it in Spotify dashboard first).
- For public apps, store credentials in the host's secret manager (or in `.streamlit/secrets.toml` which Streamlit Cloud reads). Do not commit secrets to git.
-
If you want, I can: add a GitHub Actions workflow for automatic deploy-to-Render, or prepare a small `Dockerfile` for containerized hosting. Tell me which provider you prefer and I will prepare deployment files.

Using the included redirect page

This repository includes `redirect.html`, a small static page that receives Spotify's authorization redirect and forwards the user back to the Streamlit app with the `code` query parameter. To use it:

1. Deploy the repo to Streamlit Cloud.
2. Register the redirect URI in your Spotify developer app as:

```
https://amc-board-game.streamlit.app/redirect.html
```

3. In Streamlit Cloud, set `SPOTIPY_REDIRECT_URI` to the same value (Manage app → Secrets).

When a user authorizes the app, Spotify will redirect to `/redirect.html?code=...`; the page shows confirmation and a button to return to the app so the app can finish the OAuth exchange automatically.
