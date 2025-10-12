import requests
import datetime
from config import set_sc_log_location, get_player_name
import global_variables

local_version = "7.0"
api_key = {"value": None}


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
def save_api_key(key):
    try:
        with open("killtracker_key.cfg", "w") as f:
            f.write(key)
        api_key["value"] = key  # Make sure to save the key in the global api_key dictionary as well
        global_variables.set_key(key)  # Update the global variable
        global_variables.log(f"Personal key validated and saved successfully!: {key}")
    except Exception as e:
        global_variables.log(f"Error saving API key: {e}")

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

# Load existing key from the file
@global_variables.log_exceptions
def load_existing_key():
    try:
        with open("killtracker_key.cfg", "r") as f:
            entered_key = f.readline().strip()
            if entered_key:
                api_key["value"] = entered_key
                if validate_api_key(entered_key):
                    global_variables.log("Servitor connection established")
                else:
                    global_variables.log("Invalid key. Please input a valid key")
            else:
                global_variables.log("No valid key found")
    except FileNotFoundError:
        global_variables.log("No existing key found")

# Load Existing Key
@global_variables.log_exceptions
def load_existing_key(api_status_label, rsi_handle):
    try:
        with open("killtracker_key.cfg", "r") as f:
            entered_key = f.readline().strip()
            if entered_key:
                api_key["value"] = entered_key  # Assign the loaded key
                global_variables.set_key(entered_key)  # Update the global variable
                return entered_key
            else:
                global_variables.log("No valid key found. Please enter a key.")
                api_status_label.config(text="API Status: Invalid", fg="red")
    except FileNotFoundError:
        global_variables.log("No existing key found. Please enter a valid key.")
        api_status_label.config(text="API Status: Invalid", fg="red")