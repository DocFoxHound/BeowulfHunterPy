import requests
import os
import sys
import datetime
from config import set_sc_log_location, get_player_name
import global_variables

local_version = "7.0"
api_key = {"value": None}
org_api_key = {"value": None}

# Optional custom sound paths (persisted in config lines 3, 4 & 5 if present)
custom_sound_interdiction = {"value": None}
custom_sound_nearby = {"value": None}
custom_sound_kill = {"value": None}

def _get_assets_dir() -> str:
    """Return the assets directory for default resources.

    - In PyInstaller onefile, use sys._MEIPASS/assets
    - From source, prefer project_root/assets (where project_root is parent of 'src')
    - Fallback to CWD/assets
    """
    # PyInstaller onefile extraction folder
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and os.path.isdir(meipass):
            p = os.path.join(meipass, "assets")
            if os.path.isdir(p):
                return p
    except Exception:
        pass
    # Source: try parent of src (keys.py lives in src/)
    try:
        src_dir = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(src_dir, os.pardir))
        p = os.path.join(project_root, "assets")
        if os.path.isdir(p):
            return p
    except Exception:
        pass
    # Fallback to CWD/assets
    try:
        p = os.path.join(os.getcwd(), "assets")
        return p
    except Exception:
        return "assets"


@global_variables.log_exceptions
def validate_api_key(api_key, rsi_handle):
    url = "https://beowulf.ironpoint.org/api/keys/validatekey"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    data = {
        "api_key": api_key,
        "player_name": rsi_handle  # Include the player name
    }

    try:
        response = requests.get(url, headers=headers, json=data) # TODO: post or get? Why??
        if response.status_code == 200 or response.status_code == 201:
            # Try to parse JSON and extract a user_id if present
            try:
                resp_json = response.json()
            except Exception:
                resp_json = None

            user_id = None
            # helper to extract common user id fields
            def _extract_user_id(obj):
                if not obj:
                    return None
                if isinstance(obj, dict):
                    for k in ("user_id", "userId", "geid", "player_id", "id"):
                        if k in obj and obj[k]:
                            return obj[k]
                    # common nested container keys
                    for container in ("data", "result", "results", "key"):
                        if container in obj and isinstance(obj[container], dict):
                            found = _extract_user_id(obj[container])
                            if found:
                                return found
                return None

            try:
                user_id = _extract_user_id(resp_json)
            except Exception:
                user_id = None

            if user_id:
                try:
                    global_variables.set_user_id(str(user_id))
                except Exception:
                    # swallow errors from global state set
                    pass

            # Try to extract a username and greet the user if found
            try:
                def _extract_username(obj):
                    if not obj:
                        return None
                    if isinstance(obj, dict):
                        for k in ("username", "user_name", "name", "player_name", "handle"):
                            if k in obj and obj[k]:
                                return obj[k]
                        for container in ("data", "result", "results", "key"):
                            if container in obj:
                                found = _extract_username(obj[container])
                                if found:
                                    return found
                    elif isinstance(obj, list) and len(obj) > 0:
                        # try first element
                        return _extract_username(obj[0])
                    return None

                username = _extract_username(resp_json)
                if username:
                    try:
                        global_variables.log(f"Checking key for: {username}")
                    except Exception:
                        pass
            except Exception:
                # Do not fail validation if greeting fails
                pass

            return True  # Success
        else:
            return False  # Failure
    except requests.RequestException as e:
        global_variables.log(f"API Key validation error: {e}")
        return False

@global_variables.log_exceptions
def save_api_key(key, org_key: str | None = None):
    """Save keys (line1 player, line2 org) preserving any existing custom sound paths (lines 3 & 4).

    If custom sound paths were previously stored they are re-appended. Backwards compatible with legacy 1-2 line files.
    """
    try:
        line1 = (key or "").strip()
        line2 = (org_key or "").strip()
        # Load existing to retain sound paths
        existing_lines = []
        try:
            with open("killtracker_key.cfg", "r", encoding="utf-8") as f:
                existing_lines = f.read().splitlines()
        except Exception:
            existing_lines = []

        snd_interdiction = existing_lines[2].strip() if len(existing_lines) >= 3 else (custom_sound_interdiction["value"] or "")
        snd_nearby = existing_lines[3].strip() if len(existing_lines) >= 4 else (custom_sound_nearby["value"] or "")
        snd_kill = existing_lines[4].strip() if len(existing_lines) >= 5 else (custom_sound_kill["value"] or "")
        out_lines = [line1, line2, snd_interdiction, snd_nearby, snd_kill]
        # Trim trailing empty lines while ensuring at least 2 lines persist
        while len(out_lines) > 2 and out_lines[-1] == "":
            out_lines.pop()
        with open("killtracker_key.cfg", "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines))
        api_key["value"] = line1
        org_api_key["value"] = line2 if line2 else None
        global_variables.set_key(line1)
        try:
            global_variables.set_org_key(line2 if line2 else None)
        except Exception:
            pass
        global_variables.log("Keys validated and saved successfully (player/org). Config updated.")
    except Exception as e:
        global_variables.log(f"Error saving API keys: {e}")

# Activate the API key by sending it to the server
@global_variables.log_exceptions
def activate_key(key_entry):
    global_variables.log("Activating key...")
    entered_key = global_variables.get_key().strip()  # Access key_entry here
    global_variables.log(f"Entered key: {entered_key}")  # Log the entered key for debugging
    if entered_key:
        log_file_location = set_sc_log_location()  # Assuming this is defined elsewhere
        if log_file_location:
            player_name = get_player_name(log_file_location)  # Retrieve the player name
            if player_name:
                if validate_api_key(entered_key, player_name):  # Pass both the key and player name
                    global_variables.log("API Key valid. Servitor connection established.")
                else:
                    global_variables.log("Invalid key or player name. Please enter a valid API key.")
            else:
                global_variables.log("RSI Handle not found. Please ensure the game is running and the log file is accessible.")
        else:
            global_variables.log("Log file location not found.")
    else:
        global_variables.log("No key entered. Please input a valid key.")

        

# Load Existing Key (UI-agnostic)
@global_variables.log_exceptions
def load_existing_key():
    """Load config (player key, org key, optional custom sounds).

    Returns player key for backward compatibility.
    Lines:
      1: player key
      2: org key
      3: (optional) custom interdiction sound absolute path
    4: (optional) custom nearby/player detected sound absolute path
    5: (optional) custom kill sound absolute path
    """
    try:
        with open("killtracker_key.cfg", "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        player = (lines[0].strip() if len(lines) >= 1 else "") or None
        org = (lines[1].strip() if len(lines) >= 2 else "") or None
        snd_interdiction = (lines[2].strip() if len(lines) >= 3 else "") or None
        snd_nearby = (lines[3].strip() if len(lines) >= 4 else "") or None
        api_key["value"] = player
        org_api_key["value"] = org
        # If no explicit config values, use defaults from assets folder (do not write to file)
        try:
            assets_dir = _get_assets_dir()
            if not snd_interdiction:
                cand = os.path.join(assets_dir, "interdiction detected.wav")
                if os.path.isfile(cand):
                    snd_interdiction = cand
            if not snd_nearby:
                cand = os.path.join(assets_dir, "player detected.wav")
                if os.path.isfile(cand):
                    snd_nearby = cand
            snd_kill = (lines[4].strip() if len(lines) >= 5 else "") or None
            if not snd_kill:
                cand = os.path.join(assets_dir, "kill.wav")
                if os.path.isfile(cand):
                    snd_kill = cand
        except Exception:
            pass
        custom_sound_interdiction["value"] = snd_interdiction
        custom_sound_nearby["value"] = snd_nearby
        custom_sound_kill["value"] = snd_kill
        if player:
            global_variables.set_key(player)
        try:
            global_variables.set_org_key(org)
        except Exception:
            pass
        # Propagate sound paths to globals
        try:
            global_variables.set_custom_sound_interdiction(snd_interdiction)
            global_variables.set_custom_sound_nearby(snd_nearby)
            global_variables.set_custom_sound_kill(snd_kill)
        except Exception:
            pass
        return player
    except FileNotFoundError:
        global_variables.log("No existing key found. Please enter valid keys.")
        return None

def update_sound_paths(interdiction_path: str | None, nearby_path: str | None, kill_path: str | None = None):
    """Update (or clear) custom sound paths, preserving existing keys.

    Writes a 4-line config (adding empty placeholders for missing paths) for consistency.
    """
    # Load existing keys first
    try:
        with open("killtracker_key.cfg", "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        lines = []
    player = (lines[0].strip() if len(lines) >= 1 else "")
    org = (lines[1].strip() if len(lines) >= 2 else "")
    line3 = (interdiction_path or "").strip()
    line4 = (nearby_path or "").strip()
    line5 = (kill_path or "").strip()
    # Persist
    try:
        with open("killtracker_key.cfg", "w", encoding="utf-8") as f:
            f.write("\n".join([player, org, line3, line4, line5]))
        custom_sound_interdiction["value"] = line3 or None
        custom_sound_nearby["value"] = line4 or None
        custom_sound_kill["value"] = line5 or None
        try:
            global_variables.set_custom_sound_interdiction(line3 or None)
            global_variables.set_custom_sound_nearby(line4 or None)
            global_variables.set_custom_sound_kill(line5 or None)
        except Exception:
            pass
        global_variables.log("Custom sound paths updated in config.")
    except Exception as e:
        global_variables.log(f"Failed to update custom sound paths: {e}")

def get_custom_sound_interdiction() -> str | None:
    return custom_sound_interdiction.get("value")

def get_custom_sound_nearby() -> str | None:
    return custom_sound_nearby.get("value")

def get_custom_sound_kill() -> str | None:
    return custom_sound_kill.get("value")

def get_org_key_value() -> str | None:
    return org_api_key.get("value")


@global_variables.log_exceptions
def validate_org_key(org_key: str) -> bool:
    """Validate the ORG key by calling the Star Citizen API versions endpoint.

    Endpoint: https://api.starcitizen-api.com/{org_key}/v1/cache/versions

    Returns True when the response is HTTP 200 and JSON indicates success (success == 1).
    Any non-200 status or JSON with success != 1 is treated as invalid.
    """
    if not org_key:
        return False
    url = f"https://api.starcitizen-api.com/{org_key}/v1/cache/versions"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            try:
                global_variables.log(f"ORG key validation HTTP error: {resp.status_code}")
            except Exception:
                pass
            return False
        try:
            payload = resp.json()
        except Exception:
            # If not JSON, treat as failure
            return False
        # Typical error looks like: {"data": null, "message": "Malformed request.", "source": null, "success": 0}
        if isinstance(payload, dict):
            success = payload.get("success", None)
            if success is None:
                # Some responses may omit success but include data; consider non-empty data as success
                data = payload.get("data")
                return data is not None
            return success == 1
        return False
    except requests.RequestException as e:
        global_variables.log(f"ORG Key validation error: {e}")
        return False