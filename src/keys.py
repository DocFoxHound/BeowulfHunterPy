import os
import json
import psutil
import requests
import threading
import webbrowser
import tkinter as tk
import tkinter.font as tkFont
from tkinter import scrolledtext
from tkinter import messagebox
import sys
from packaging import version
import time
import datetime
from dotenv import load_dotenv
from PIL import Image, ImageTk
from config import set_sc_log_location, get_player_name
import global_variables

logger = global_variables.get_logger()

local_version = "7.0"
api_key = {"value": None}


def validate_api_key(api_key, rsi_handle):
    url = os.getenv("KEY_VALIDATE_URL")
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
    entered_key = key_entry.get().strip()  # Access key_entry here
    logger.log(f"Entered key: {entered_key}")  # Log the entered key for debugging
    if entered_key:
        log_file_location = set_sc_log_location()  # Assuming this is defined elsewhere
        if log_file_location:
            player_name = get_player_name(log_file_location)  # Retrieve the player name
            if player_name:
                if validate_api_key(entered_key, player_name):  # Pass both the key and player name
                    save_api_key(entered_key, logger)  # Save the key for future use
                    logger.log("Key activated and saved. Servitor connection established.")
                else:
                    logger.log("Invalid key or player name. Please enter a valid API key.")
            else:
                logger.log("RSI Handle not found. Please ensure the game is running and the log file is accessible.")
        else:
            logger.log("Log file location not found.")
    else:
        logger.log("No key entered. Please input a valid key.")

# # Load existing key from the file
# def load_existing_key():
#     try:
#         with open("killtracker_key.cfg", "r") as f:
#             entered_key = f.readline().strip()
#             if entered_key:
#                 api_key["value"] = entered_key
#                 logger.log("Existing key loaded. Attempting to establish Servitor connection...")
#                 if validate_api_key(entered_key):
#                     logger.log("Servitor connection established.")
#                 else:
#                     logger.log("Invalid key. Please input a valid key.")
#             else:
#                 logger.log("No valid key found. Please enter a key.")
#     except FileNotFoundError:
#         logger.log("No existing key found. Please enter a valid key.")

# Load Existing Key
def load_existing_key(api_status_label, rsi_handle):
    logger = global_variables.get_logger()
    try:
        with open("killtracker_key.cfg", "r") as f:
            entered_key = f.readline().strip()
            if entered_key:
                api_key["value"] = entered_key  # Assign the loaded key
                global_variables.set_key(entered_key)  # Update the global variable
                logger.log(f"Existing key loaded: {entered_key}. Attempting to establish Servitor connection...")
                if validate_api_key(entered_key, get_player_name(set_sc_log_location())):  # Validate with player name
                    logger.log("Servitor connection established.")
                    api_status_label.config(text="API Status: Valid (Expires in 72 hours)", fg="green")
                    start_api_key_countdown(entered_key, api_status_label, rsi_handle)
                else:
                    logger.log("Invalid key. Please input a valid key.")
                    api_status_label.config(text="API Status: Invalid", fg="red")
            else:
                logger.log("No valid key found. Please enter a key.")
                api_status_label.config(text="API Status: Invalid", fg="red")
    except FileNotFoundError:
        logger.log("No existing key found. Please enter a valid key.")
        api_status_label.config(text="API Status: Invalid", fg="red")


def start_api_key_countdown(api_key, api_status_label, rsi_handle):
    """
    Function to start the countdown for the API key's expiration, refreshing expiry data periodically.
    """
    def update_countdown():
        expiration_time = get_api_key_expiration_time(api_key, rsi_handle)  # Fetch latest expiration time
        if not expiration_time:
            api_status_label.config(text="API Status: Expired", fg="red")
            return

        def countdown():
            remaining_time = expiration_time - datetime.datetime.utcnow()
            if remaining_time.total_seconds() > 0:
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                countdown_text = f"API Status: Valid (Expires in {remaining_time.days}d {hours}h {minutes}m {seconds}s)"
                api_status_label.config(text=countdown_text, fg="green")
                api_status_label.after(1000, countdown)  # Update every second
            else:
                api_status_label.config(text="API Status: Expired", fg="red")

        countdown()

        # Refresh expiration time every 60 seconds to stay in sync with the server
        api_status_label.after(60000, update_countdown)

    update_countdown()

def get_api_key_expiration_time(api_key, rsi_handle):
    """
    Retrieve the expiration time for the API key from the validation server.
    """
    url = os.getenv("KEY_VALIDATE_URL")
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    data = {
        "player_name": rsi_handle
    }

    try:
        response = requests.get(url, headers=headers, json=data)
        print(f"\n{response}\n")

        if response.status_code == 200:
            response_data = response.json()
            expiration_time_str = response_data.get("expires_at")
            if expiration_time_str:
                return datetime.datetime.strptime(expiration_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                print("Error: 'expires_at' not found in response")
        else:
            print("Error fetching expiration time:", response.json().get("error", "Unknown error"))
    except requests.RequestException as e:
        print(f"API request error: {e}")

    # Fallback: Expire immediately if there's an error
    return None