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
import global_variables


def game_heartbeat(check_interval, game_running):
    logger = global_variables.get_logger()
    """Check every X seconds if the game is running. When detected, trigger callback."""
    def heartbeat_loop():
        while game_running:
            if is_game_running():
                time.sleep(check_interval)
                continue
            if is_game_running() is None:
                logger.log("Game Crashed")
                while is_game_running() is None:
                    logger.log("Waiting for StarCitizen...")
                    game_running_check = is_game_running()
                    time.sleep(check_interval)
                logger.log("Game is running again.")
                on_game_relaunch()
                continue


    threading.Thread(target=heartbeat_loop, daemon=True).start()

def on_game_relaunch():
    logger = global_variables.get_logger()
    # Reset necessary state, you can expand this
    # new_log_file_location = set_sc_log_location()
    global_variables.set_log_file_location(set_sc_log_location())
    logger.log("Game relaunched. Updating log file location.")