import os
import sys

# Add the 'src' directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import json
import psutil
import requests
import threading
import webbrowser
import tkinter as tk
import tkinter.font as tkFont
from tkinter import scrolledtext
from tkinter import messagebox
from packaging import version
import time
import datetime
from dotenv import load_dotenv
from PIL import Image, ImageTk
from config import set_sc_log_location, auto_shutdown, find_rsi_handle, is_game_running
from parser import start_tail_log_thread
from setup_gui import setup_gui
from crash_detection import game_heartbeat
import global_variables

load_dotenv() # Load environment variables from .env file
# API_KEY = os.getenv("API_KEY") # Example how to use the .env file

local_version = "7.0"
api_key = {"value": None}

class EventLogger:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def log(self, message):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, message + "\n")
        self.text_widget.config(state=tk.DISABLED)
        self.text_widget.see(tk.END)

if __name__ == '__main__':
    game_running = is_game_running() # check processes to see if the game's running    

    app, logger = setup_gui(game_running) # setup the GUI or logger

    if game_running:
        # log_file_location = set_sc_log_location()
        # Start log monitoring in a separate thread
        global_variables.set_log_file_location(set_sc_log_location()) # Set the log file location in global variables
        log_file_location = global_variables.get_log_file_location()
        if log_file_location:
            rsi_handle = find_rsi_handle(log_file_location)
            if rsi_handle:
                start_tail_log_thread(log_file_location, rsi_handle)
                game_heartbeat(1, True)

    
    # Initiate auto-shutdown after 72 hours (72 * 60 * 60 seconds)
    if logger:
        auto_shutdown(app, 72 * 60 * 60, logger)  # Pass logger only if initialized
    else:
        auto_shutdown(app, 72 * 60 * 60)  # Fallback without logger

    app.mainloop()
