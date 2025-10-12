import os
import sys

# Add the 'src' directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import threading
import time
from config import set_sc_log_location, auto_shutdown, find_rsi_handle, is_game_running
import global_variables


@global_variables.log_exceptions
def game_heartbeat(check_interval, game_running):
    """Check every X seconds if the game is running. When detected, trigger callback."""
    def heartbeat_loop():
        while game_running:
            if is_game_running():
                time.sleep(check_interval)
                continue
            if is_game_running() is None:
                global_variables.log("Game Crashed")
                global_variables.log("Will resume monitoring game.log once game is re-launched.")
                while is_game_running() is None:
                    game_running_check = is_game_running()
                    time.sleep(check_interval)
                global_variables.log("Game is running again.")
                on_game_relaunch()
                continue


    threading.Thread(target=heartbeat_loop, daemon=True).start()

@global_variables.log_exceptions
def on_game_relaunch():
    # Reset necessary state, you can expand this
    global_variables.set_log_file_location(set_sc_log_location())
    global_variables.log("🗹 Game relaunched")