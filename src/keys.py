import requests
import datetime
from config import set_sc_log_location, get_player_name
import global_variables

local_version = "7.0"
api_key = {"value": None}
org_api_key = {"value": None}


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
    """Save the player key on the first line and the org key on the second line.

    If org_key is None, we still write a trailing newline to keep two-line format.
    """
    try:
        line1 = (key or "").strip()
        line2 = (org_key or "").strip()
        with open("killtracker_key.cfg", "w", encoding="utf-8") as f:
            f.write(line1 + "\n" + line2)
        api_key["value"] = line1
        org_api_key["value"] = line2 if line2 else None
        global_variables.set_key(line1)
        try:
            global_variables.set_org_key(line2 if line2 else None)
        except Exception:
            pass
        global_variables.log("Keys validated and saved successfully (player/org).")
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
    """Load player and org keys from cfg; return player key for backward compatibility.

    Side effects: sets global_variables.set_key and set_org_key when available.
    """
    try:
        with open("killtracker_key.cfg", "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        player = (lines[0].strip() if len(lines) >= 1 else "") or None
        org = (lines[1].strip() if len(lines) >= 2 else "") or None
        api_key["value"] = player
        org_api_key["value"] = org
        if player:
            global_variables.set_key(player)
        try:
            global_variables.set_org_key(org)
        except Exception:
            pass
        return player
    except FileNotFoundError:
        global_variables.log("No existing key found. Please enter valid keys.")
        return None

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