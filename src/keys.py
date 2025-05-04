import requests
import datetime
from config import set_sc_log_location, get_player_name
import global_variables

logger = global_variables.get_logger()

local_version = "7.0"
api_key = {"value": None}


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
            return True  # Success
        else:
            return False  # Failure
    except requests.RequestException as e:
        print(f"API Key validation error: {e}")
        return False

def save_api_key(key):
    logger = global_variables.get_logger()
    try:
        with open("killtracker_key.cfg", "w") as f:
            f.write(key)
        api_key["value"] = key  # Make sure to save the key in the global api_key dictionary as well
        global_variables.set_key(key)  # Update the global variable
        logger.log(f"API key saved successfully: {key}")
    except Exception as e:
        logger.log(f"Error saving API key: {e}")

# Activate the API key by sending it to the server
def activate_key(key_entry):
    logger = global_variables.get_logger()
    logger.log("Activating key...")
    entered_key = global_variables.get_key().strip()  # Access key_entry here
    logger.log(f"Entered key: {entered_key}")  # Log the entered key for debugging
    if entered_key:
        log_file_location = set_sc_log_location()  # Assuming this is defined elsewhere
        if log_file_location:
            player_name = get_player_name(log_file_location)  # Retrieve the player name
            if player_name:
                if validate_api_key(entered_key, player_name):  # Pass both the key and player name
                    logger.log("API Key valid. Servitor connection established.")
                else:
                    logger.log("Invalid key or player name. Please enter a valid API key.")
            else:
                logger.log("RSI Handle not found. Please ensure the game is running and the log file is accessible.")
        else:
            logger.log("Log file location not found.")
    else:
        logger.log("No key entered. Please input a valid key.")

# Load existing key from the file
def load_existing_key():
    try:
        with open("killtracker_key.cfg", "r") as f:
            entered_key = f.readline().strip()
            if entered_key:
                api_key["value"] = entered_key
                logger.log("Existing key loaded")
                if validate_api_key(entered_key):
                    logger.log("Servitor connection established")
                else:
                    logger.log("Invalid key. Please input a valid key")
            else:
                logger.log("No valid key found")
    except FileNotFoundError:
        logger.log("No existing key found")

# Load Existing Key
def load_existing_key(api_status_label, rsi_handle):
    logger = global_variables.get_logger()
    try:
        with open("killtracker_key.cfg", "r") as f:
            entered_key = f.readline().strip()
            if entered_key:
                api_key["value"] = entered_key  # Assign the loaded key
                global_variables.set_key(entered_key)  # Update the global variable
                logger.log(f"Existing key loaded")
                return entered_key
            else:
                logger.log("No valid key found. Please enter a key.")
                api_status_label.config(text="API Status: Invalid", fg="red")
    except FileNotFoundError:
        logger.log("No existing key found. Please enter a valid key.")
        api_status_label.config(text="API Status: Invalid", fg="red")