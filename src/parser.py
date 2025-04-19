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
import global_variables

local_version = "7.0"
api_key = {"value": None}

# Substrings to ignore
ignore_kill_substrings = [
    'PU_Pilots',
    'NPC_Archetypes',
    'PU_Human',
    'kopion',
    'marok',
]

global_ship_list = [
    'DRAK', 'ORIG', 'AEGS', 'ANVL', 'CRUS', 'BANU', 'MISC',
    'KRIG', 'XNAA', 'ARGO', 'VNCL', 'ESPR', 'RSI', 'CNOU',
    'GRIN', 'TMBL', 'GAMA'
]

global_game_mode = "Nothing"
global_active_ship = "N/A"
global_active_ship_id = "N/A"
global_player_geid = "N/A"

def start_tail_log_thread(log_file_location, rsi_name):
    """Start the log tailing in a separate thread."""
    thread = threading.Thread(target=tail_log, args=(log_file_location, rsi_name))
    thread.daemon = True
    thread.start()

def tail_log(log_file_location, rsi_name):
    logger = global_variables.get_logger()
    """Read the log file and display events in the GUI."""
    global global_game_mode, global_player_geid
    sc_log = open(log_file_location, "r")
    if sc_log is None:
        logger.log(f"No log file found at {log_file_location}.")
        return

    logger.log("Kill Tracking Initiated...")
    logger.log("Enter key to establish Servitor connection...")

    # Read all lines to find out what game mode player is currently, in case they booted up late.
    # Don't upload kills, we don't want repeating last sessions kills incase they are actually available.
    lines = sc_log.readlines()
    print("Loading old log (if available)! Kills shown will not be uploaded as they are stale.")
    for line in lines:
        read_log_line(line, rsi_name, False)

    # Main loop to monitor the log
    last_log_file_size = os.stat(log_file_location).st_size
    while True:
        where = sc_log.tell()
        line = sc_log.readline()
        if not line:
            time.sleep(1)
            sc_log.seek(where)
            if last_log_file_size > os.stat(log_file_location).st_size:
                sc_log.close()
                sc_log = open(log_file_location, "r")
                last_log_file_size = os.stat(log_file_location).st_size
        else:
            read_log_line(line, rsi_name, True)

def read_existing_log(log_file_location, rsi_name):
    sc_log = open(log_file_location, "r")
    lines = sc_log.readlines()
    for line in lines:
        read_log_line(line, rsi_name, True)

# Trigger kill event
def parse_kill_line(line, target_name):
    key = global_variables.get_key()
    logger = global_variables.get_logger()
    api_key['value'] = key
    print(f"Current API Key: {api_key['value']}")

    if not check_exclusion_scenarios(line, logger):
        return

    split_line = line.split(' ')
#  <2025-04-13T17:17:51.279Z> [Notice] <Actor Death> CActor::Kill: 'Mercuriuss' [200146297631] in zone 'ANVL_Hornet_F7A_Mk2_2677329226210' killed by 'DocHound' [202061381370] using 'GATS_BallisticGatling_S3_2677329225797' [Class unknown] with damage type 'VehicleDestruction' from direction x: 0.000000, y: 0.000000, z: 0.000000 [Team_ActorTech][Actor]
#  <2025-04-14T16:42:53.465Z> [Notice] <Actor Death> CActor::Kill: 'idkausername_27' [202063593546] in zone 'OOC_Stanton_2a_Cellin' killed by 'DocHound' [202061381370] using 'lbco_pistol_energy_01_2698343630880' [Class lbco_pistol_energy_01] with damage type 'Bullet' from direction x: -0.995284, y: -0.073818, z: -0.062935 [Team_ActorTech][Actor]
#  <2025-04-14T17:10:51.498Z> [Notice] <Actor Death> CActor::Kill: 'Mercuriuss' [200146297631] in zone 'ANVL_Hornet_F7A_Mk2_2699085238610' killed by 'DocHound' [202061381370] using 'RSI_Bespoke_BallisticCannon_A_2699085238957' [Class unknown] with damage type 'VehicleDestruction' from direction x: 0.000000, y: 0.000000, z: 0.000000 [Team_ActorTech][Actor]
#  <2025-04-14T17:16:18.806Z> [Notice] <Actor Death> CActor::Kill: 'Mercuriuss' [200146297631] in zone 'ANVL_Hornet_F7A_Mk2_2699085240659' killed by 'DocHound' [202061381370] using 'MRCK_S10_RSI_Polaris_Torpedo_lb_2699085238828' [Class MRCK_S10_RSI_Polaris_Torpedo_lb] with damage type 'Explosion' from direction x: 0.383955, y: 1.041579, z: -0.330675 [Team_ActorTech][Actor]
#  <2025-04-14T18:27:04.421Z> [Notice] <Actor Death> CActor::Kill: 'Mercuriuss' [200146297631] in zone 'SolarSystem_2700185231297' killed by 'DocHound' [202061381370] using 'unknown' [Class unknown] with damage type 'Explosion' from direction x: -0.874768, y: -2.434404, z: 0.141657 [Team_ActorTech][Actor] ::: grenade kill

    kill_time = split_line[0].strip('\'')
    killed = split_line[5].strip('\'')
    killed_zone = split_line[9].strip('\'')
    killer = split_line[12].strip('\'')
    weapon = split_line[15].strip('\'')
    damage_type = split_line[21].strip('\'')

    if killed == killer or killer.lower() == "unknown" or killed == target_name:
        logger.log("You DIED.")
        return

    event_message = f"You have killed {killed},"
    logger.log(event_message)
    json_data = {
        'player': target_name,
        'victim': killed,
        'time': kill_time,
        'zone': killed_zone,
        'weapon': weapon,
        'rsi_profile': f"https://robertsspaceindustries.com/citizens/{killed}",
        'game_mode': global_game_mode,
        'client_ver': "7.0",
        'killers_ship': global_active_ship,
        'damage_type': damage_type
    }

    headers = {
        'content-type': 'application/json',
        'Authorization': api_key["value"] if api_key["value"] else ""
    }

    if not api_key["value"]:
        logger.log("Kill event will not be sent. Enter valid key to establish connection with Servitor...")
        return

    try:
        response = requests.post(
            os.getenv("REPORT_KILL_URL"),
            headers=headers,
            data=json.dumps(json_data)
        )
        if response.status_code == 200 or response.status_code == 201:
            logger.log("Kill logged.")
        else:
            # logger.log(f"Servitor connectivity error: {response.status_code}.")
            logger.log("Relaunch BeowulfHunter and reconnect with a new Key.")
    except requests.exceptions.RequestException as e:
        logger.log(f"Error sending kill event: {e}")
        # logger.log("Kill event will not be sent. Please ensure a valid key and try again.")

def check_substring_list(line, substring_list):
    """
    Check if any substring from the list is present in the given line.
    """
    for substring in substring_list:
        if substring.lower() in line.lower():
            return True
    return False

def check_exclusion_scenarios(line, logger):
    global global_game_mode
    if global_game_mode == "EA_FreeFlight" and -1 != line.find("Crash"):
        print("Probably a ship reset, ignoring kill!")
        return False
    return True

def find_rsi_geid(log_file_location):
    global global_player_geid
    acct_kw = "AccountLoginCharacterStatus_Character"
    sc_log = open(log_file_location, "r")
    lines = sc_log.readlines()
    for line in lines:
        if -1 != line.find(acct_kw):
            global_player_geid = line.split(' ')[11]
            print("Player geid: " + global_player_geid)
            return

def set_game_mode(line):
    global global_game_mode
    global global_active_ship
    global global_active_ship_id
    split_line = line.split(' ')
    game_mode = split_line[8].split("=")[1].strip("\"")
    if game_mode != global_game_mode:
        global_game_mode = game_mode

    if "SC_Default" == global_game_mode:
        global_active_ship = "N/A"
        global_active_ship_id = "N/A"

def read_log_line(line, rsi_name, upload_kills):
    if -1 != line.find("<Context Establisher Done>"):
        set_game_mode(line)
    elif -1 != line.find(rsi_name):
        if -1 != line.find("OnEntityEnterZone"):
            set_player_zone(line)
        if -1 != line.find("CActor::Kill") and not check_substring_list(line, ignore_kill_substrings) and upload_kills:
            parse_kill_line(line, rsi_name)
    elif -1 != line.find("CPlayerShipRespawnManager::OnVehicleSpawned") and (
            "SC_Default" != global_game_mode) and (-1 != line.find(global_player_geid)):
        set_ac_ship(line)
    elif ((-1 != line.find("<Vehicle Destruction>")) or (
            -1 != line.find("<local client>: Entering control state dead"))) and (
            -1 != line.find(global_active_ship_id)):
        destroy_player_zone(line)


def destroy_player_zone(line):
    global global_active_ship
    global global_active_ship_id
    if ("N/A" != global_active_ship) or ("N/A" != global_active_ship_id):
        print(f"Ship Destroyed: {global_active_ship} with ID: {global_active_ship_id}")
        global_active_ship = "N/A"
        global_active_ship_id = "N/A"

def set_ac_ship(line):
    global global_active_ship
    global_active_ship = line.split(' ')[5][1:-1]
    print("Player has entered ship: ", global_active_ship)

def set_player_zone(line):
    global global_active_ship
    global global_active_ship_id
    line_index = line.index("-> Entity ") + len("-> Entity ")
    if 0 == line_index:
        print("Active Zone Change: ", global_active_ship)
        global_active_ship = "N/A"
        return
    potential_zone = line[line_index:].split(' ')[0]
    potential_zone = potential_zone[1:-1]
    for x in global_ship_list:
        if potential_zone.startswith(x):
            global_active_ship = potential_zone[:potential_zone.rindex('_')]
            global_active_ship_id = potential_zone[potential_zone.rindex('_') + 1:]
            print(f"Active Zone Change: {global_active_ship} with ID: {global_active_ship_id}")
            return
        
