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
from config import set_sc_log_location, get_player_name, find_rsi_handle
from keys import validate_api_key, save_api_key, start_api_key_countdown, load_existing_key
import global_variables
from crash_detection import game_heartbeat, on_game_relaunch

local_version = "7.0"  # You could pass this as a parameter if needed
class EventLogger:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def log(self, message):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, message + "\n")
        self.text_widget.config(state=tk.DISABLED)
        self.text_widget.see(tk.END)
        
def setup_gui(game_running):
    app = tk.Tk()
    app.title("BeowulfHunter")
    app.geometry("650x450")
    app.resizable(False, False)
    app.configure(bg="#1a1a1a")

    

    try:
        font_path = resource_path("../Orbitron.ttf")
        custom_font = tkFont.Font(file=font_path, size=12)
        app.option_add("*Font", custom_font)
    except Exception as e:
        print(f"Failed to load custom font: {e}")

    # Set the icon
    try:
        icon_path = resource_path("beo.ico")
        print("Resolved icon path:", icon_path)
        if os.path.exists(icon_path):
            app.iconbitmap(icon_path)
            print(f"Icon loaded successfully from: {icon_path}")
        else:
            print(f"Icon not found at: {icon_path}")
    except Exception as e:
        print(f"Error setting icon: {e}")

    # Add Banner
    try:
        banner_path = resource_path("beohunter.png")
        original_image = Image.open(banner_path)

        # Resize to 50% of original size (or change to specific size like (600, 150))
        resized_image = original_image.resize((480, 150), Image.Resampling.LANCZOS)

        banner_image = ImageTk.PhotoImage(resized_image)
        banner_label = tk.Label(app, image=banner_image, bg="#1a1a1a")
        banner_label.image = banner_image
        banner_label.pack(pady=(0, 10))
    except Exception as e:
        print(f"Error loading banner image: {e}")

    # Check for Updates
    update_message = check_for_updates()
    if update_message:
        update_label = tk.Label(
            app,
            text=update_message,
            font=("Times New Roman", 12),
            fg="#ff5555",
            bg="#1a1a1a",
            wraplength=700,
            justify="center",
            cursor="hand2",
        )
        update_label.pack(pady=(10, 10))
        update_label.bind("<Button-1>", lambda event: open_github(event, update_message))
        # update_label.bind("<Button-1>", open_github)

    if game_running:
        global_variables.set_log_file_location(set_sc_log_location()) # Set the log file location in global variables
        log_file_location = global_variables.get_log_file_location()
        global_variables.set_rsi_handle(find_rsi_handle(log_file_location))  # Retrieve the player name
        rsi_handle = global_variables.get_rsi_handle()  # Retrieve the player name
        player_name = get_player_name(log_file_location)
        
        # API Key Input
        key_frame = tk.Frame(app, bg="#1a1a1a")
        key_frame.pack(pady=(10, 10))

        key_label = tk.Label(
            key_frame, text="Enter Key:", font=("Times New Roman", 12), fg="#ffffff", bg="#1a1a1a"
        )
        key_label.pack(side=tk.LEFT, padx=(0, 5))

        # key_entry = tk.Entry(key_frame, width=30, font=("Times New Roman", 12))
        key_entry = tk.Entry(
            key_frame,
            width=30,
            font=("Orbitron", 12),
            highlightthickness=2,
            highlightbackground="#ff0000",
            highlightcolor="#ff0000",
            bg="#0a0a0a",
            fg="#ffffff",
            insertbackground="#ff5555"
        )
        key_entry.pack(side=tk.LEFT)

        # API Status Label
        api_status_label = tk.Label(
            app,
            text="API Status: Not Validated",
            font=("Times New Roman", 12),
            fg="#ffffff",
            bg="#1a1a1a",
        )
        api_status_label.pack(pady=(10, 10))

        # Activate API Key
        def activate_key():
            entered_key = key_entry.get().strip()  # Access key_entry here
            if entered_key:
                # log_file_location = set_sc_log_location()  # Assuming this is defined elsewhere
                if log_file_location:
                    # player_name = get_player_name(log_file_location)
                    # rsi_handle = find_rsi_handle(log_file_location)  # Retrieve the player name
                    if player_name:
                        if validate_api_key(entered_key, rsi_handle):  # Pass both the key and player name
                            save_api_key(entered_key)  # Save the key for future use
                            global_variables.set_key(entered_key)  # Set the key in the global state
                            logger.log("Key activated and saved. Servitor connection established.")
                            api_status_label.config(text="API Status: Valid (Expires in 72 hours)", fg="green")
                            start_api_key_countdown(entered_key, api_status_label, rsi_handle)
                        else:
                            logger.log("Invalid key. Please enter a valid API key.")
                            api_status_label.config(text="API Status: Invalid", fg="red")
                    else:
                        logger.log("RSI Handle not found. Please ensure the game is running and the log file is accessible.")
                        api_status_label.config(text="API Status: Error", fg="yellow")
                else:
                    logger.log("Log file location not found.")
                    api_status_label.config(text="API Status: Error", fg="yellow")
            else:
                logger.log("No key entered. Please input a valid key.")
                api_status_label.config(text="API Status: Invalid", fg="red")
        
        button_style = {
            "bg": "#0f0f0f",
            "fg": "#ff5555",
            "activebackground": "#330000",
            "activeforeground": "#ffffff",
            "relief": "ridge",
            "bd": 2,
            "font": ("Orbitron", 12)
        }
        
        activate_button = tk.Button(
            key_frame,
            text="Activate",
            command=activate_key,
            **button_style
        )
        activate_button.pack(side=tk.LEFT, padx=(5, 0))

        button_style = {
            "bg": "#0f0f0f",
            "fg": "#ff5555",
            "activebackground": "#330000",
            "activeforeground": "#ffffff",
            "relief": "ridge",
            "bd": 2,
            "font": ("Orbitron", 12)
        }

        load_key_button = tk.Button(
            key_frame,
            text="Load Existing Key",


            command=lambda: load_existing_key(api_status_label, rsi_handle),  # Use lambda to delay execution
            **button_style
        )
        load_key_button.pack(side=tk.LEFT, padx=(5, 0))

        # Log Display
        text_area = scrolledtext.ScrolledText(
            app,
            wrap=tk.WORD,
            width=80,
            height=20,
            state=tk.DISABLED,
            bg="#121212",
            fg="#ff4444",
            insertbackground="#ff4444",
            highlightthickness=2,
            highlightbackground="#ff0000",
            highlightcolor="#ff0000",
            font=("Orbitron", 12)
        )
        text_area.pack(padx=10, pady=10)

        global_variables.set_logger(text_area)  # Set the logger in the global state
        logger = global_variables.get_logger()  # Get the logger from the global state
        # logger = EventLogger(text_area)

    else:
        # Relaunch Message
        message_label = tk.Label(
            app,
            text="You must launch Star Citizen before starting the tracker.\n\nPlease close this window, launch Star Citizen, and relaunch BeowulfHunter. ",
            font=("Times New Roman", 14),
            fg="#ff4444",
            bg="#1a1a1a",
            wraplength=700,
            justify="center",
        )
        message_label.pack(pady=(50, 10))
        logger = None

    # Footer
    footer = tk.Frame(app, bg="#3e3b4d", height=30)
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    footer_text = tk.Label(
        footer,
        text="BeowulfHunter is a clone of BlightVeil's KillTracker - Credits: BlightVeil: (CyberBully-Actual, BossGamer09, Holiday)",
        font=("Times New Roman", 10),
        fg="#bcbcd8",
        bg="#3e3b4d",
    )
    footer_text.pack(pady=5)

    return app, logger

def resource_path(relative_path):
    """ Get the absolute path to the resource (works for PyInstaller .exe). """
    try:
        base_path = sys._MEIPASS  
    except AttributeError:
        base_path = os.path.abspath(".")  
    return os.path.join(base_path, relative_path)

def check_for_updates():
    """Check for updates using the GitHub API."""
    github_api_url = "https://api.github.com/repos/docfoxhound/BeowulfHunterPy/releases/latest"

    try:
        headers = {'User-Agent': 'BeowulfHunter/1.0'}
        response = requests.get(github_api_url, headers=headers, timeout=5)

        if response.status_code == 200:
            release_data = response.json()
            remote_version = release_data.get("tag_name", "v1.0").strip("v")
            download_url = release_data.get("html_url", "")

            if version.parse(local_version) < version.parse(remote_version):
                return f"Update available: {remote_version}. Download it here: {download_url}"
        else:
            print(f"GitHub API error: {response.status_code}")
    except Exception as e:
        print(f"Error checking for updates: {e}")
    return None

def open_github(event, update_message):
            try:
                url = update_message.split("Download it here: ")[-1]
                webbrowser.open(url)
            except Exception as e:
                print(f"Error opening GitHub link: {e}")