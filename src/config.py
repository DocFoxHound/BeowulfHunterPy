import os
import psutil
import threading
import sys
import time

import global_variables


@global_variables.log_exceptions
def set_sc_log_location():
    """ Check for RSI Launcher and Star Citizen Launcher, and set SC_LOG_LOCATION accordingly. """
    # Check if RSI Launcher is running
    rsi_launcher_path = check_if_process_running("RSI Launcher")
    if not rsi_launcher_path:
        global_variables.log("RSI Launcher not running.")
        return None

    # Check if Star Citizen Launcher is running
    sc_launcher_path = check_if_process_running("StarCitizen")
    if not sc_launcher_path:
        global_variables.log("Star Citizen Launcher not running.")
        return None

    # Search for Game.log in the folder next to StarCitizen_Launcher.exe
    star_citizen_dir = os.path.dirname(sc_launcher_path)
    log_path = find_game_log_in_directory(star_citizen_dir)

    if log_path:
        os.environ['SC_LOG_LOCATION'] = log_path
        return log_path
    else:
        global_variables.log("Game.log not found in expected locations.")
        return None
    
@global_variables.log_exceptions
def find_game_log_in_directory(directory):
    """ Search for Game.log in the directory and its parent directory. """
    game_log_path = os.path.join(directory, 'Game.log')
    if os.path.exists(game_log_path):
        return game_log_path
    # If not found in the same directory, check the parent directory
    parent_directory = os.path.dirname(directory)
    game_log_path = os.path.join(parent_directory, 'Game.log')
    if os.path.exists(game_log_path):
        global_variables.log(f"Found Game.log in parent directory: {parent_directory}")
        return game_log_path
    return None





@global_variables.log_exceptions
def auto_shutdown(app, delay_in_seconds, logger=None):
    def shutdown():
        time.sleep(delay_in_seconds) 
        if logger:
            logger.log("Application has been open for 72 hours. Shutting down in 60 seconds.") 
        else:
            try:
                import global_variables
                global_variables.log("Application has been open for 72 hours. Shutting down in 60 seconds.")
            except Exception:
                global_variables.log("Application has been open for 72 hours. Shutting down in 60 seconds.")  

        time.sleep(60)

        app.quit() 
        sys.exit(0) 

    # Run the shutdown logic in a separate thread
    shutdown_thread = threading.Thread(target=shutdown, daemon=True)
    shutdown_thread.start()

@global_variables.log_exceptions
def check_if_process_running(process_name):
    """ Check if a process is running by name. """
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        if process_name.lower() in proc.info['name'].lower():
            return proc.info['exe']
    return None

@global_variables.log_exceptions
def find_rsi_handle(log_file_location):
    acct_str = "<Legacy login response> [CIG-net] User Login Success"
    sc_log = open(log_file_location, "r")
    lines = sc_log.readlines()
    for line in lines:
        if -1 != line.find(acct_str):
            line_index = line.index("Handle[") + len("Handle[")
            if 0 == line_index:
                global_variables.log("RSI_HANDLE: Not Found!")
                exit()
            potential_handle = line[line_index:].split(' ')[0]
            return potential_handle[0:-1]
    return None

@global_variables.log_exceptions
def is_game_running():
    """Check if Star Citizen is running."""
    GAME_PROCESS_NAME = "StarCitizen"
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        if GAME_PROCESS_NAME.lower() in proc.info['name'].lower():
            return proc.info['exe']
    return None

@global_variables.log_exceptions
def get_player_name(log_file_location):
    # Retrieve the RSI handle using the existing function
    rsi_handle = find_rsi_handle(log_file_location)
    if not rsi_handle:
        global_variables.log("Error: RSI handle not found.")
        return None
    return rsi_handle