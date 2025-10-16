import os
import json
import requests
import threading
import time
import re
import global_variables
from datetime import datetime, timezone, timedelta

local_version = "7.0"
api_key = {"value": None}
# Cache of kills fetched from the API for the current run. Stored as set of
# (victim, timestamp) tuples for fast duplicate checks by other functions.
api_kills_cache = set()

# Holds the most recent vehicle destruction context attributed to the local player,
# so we can attach accurate location/coordinates to the next kill event.
last_vehicle_context = {
    'zone': None,          # e.g., 'ellis3'
    'coordinates': None,   # e.g., "-580645.384869,141765.234817,806351.274790"
    'time': None,          # timestamp string from the log line
    'killer': None         # name of the player who caused the destruction
}


@global_variables.log_exceptions
def update_vehicle_destruction_context(line, rsi_name=None):
    """Parse a '<Vehicle Destruction>' log line and, if caused by the local player,
    store its zone and coordinates for subsequent kill events.

    Expected format example:
    <2024-11-02T15:10:12.427Z> [Notice] <Vehicle Destruction> ... in zone 'ellis3' [pos x: -580645.384869, y: 141765.234817, z: 806351.274790 vel x: ...] ... caused by 'DocHound' [...]
    """
    try:
        # Only consider lines that actually contain the marker
        if "<Vehicle Destruction>" not in line:
            return

        # Extract the timestamp between leading < and >
        timestamp_match = re.search(r"^<([^>]+)>", line)
        ts = timestamp_match.group(1) if timestamp_match else None

        # Extract the zone name inside in zone '...' (first occurrence)
        zone_match = re.search(r"in zone '([^']+)'", line)
        zone = zone_match.group(1) if zone_match else None

        # Extract coordinates following [pos x: <x>, y: <y>, z: <z>
        coords_match = re.search(r"\[pos x:\s*([-\d\.]+),\s*y:\s*([-\d\.]+),\s*z:\s*([-\d\.]+)", line)
        coords = None
        if coords_match:
            try:
                x, y, z = coords_match.group(1), coords_match.group(2), coords_match.group(3)
                # Store as a compact comma-separated string for transport/UI simplicity
                coords = f"{x},{y},{z}"
            except Exception:
                coords = None

        # Extract the actor who caused the destruction: caused by 'NAME'
        killer_match = re.search(r"caused by '([^']+)'", line)
        caused_by = killer_match.group(1) if killer_match else None

        # If we were given a target RSI name, only capture if this VD was caused by the local player
        if rsi_name and caused_by and caused_by.lower() != str(rsi_name).lower():
            return

        # If we have at least zone or coordinates, store/update the context
        if zone or coords:
            last_vehicle_context['zone'] = zone
            last_vehicle_context['coordinates'] = coords
            last_vehicle_context['time'] = ts
            last_vehicle_context['killer'] = caused_by
            try:
                # Keep this log light to avoid noise
                if zone and coords:
                    global_variables.log(f"Captured VD context — location: {zone}, coords: {coords}")
                elif zone:
                    global_variables.log(f"Captured VD context — location: {zone}")
                elif coords:
                    global_variables.log(f"Captured VD context — coords: {coords}")
            except Exception:
                pass
    except Exception as e:
        try:
            global_variables.log(f"update_vehicle_destruction_context error: {e}")
        except Exception:
            pass


@global_variables.log_exceptions
def get_user_kills_from_api(user_id):
    """Fetch existing kills for a user from the Beowulf blackbox API.

    Returns a set of (victim, time) tuples for quick duplicate checking. If
    anything goes wrong or the response format is unexpected, an empty set
    is returned and parsing proceeds normally.
    """
    # If caller didn't provide a user_id, try to read it from global variables
    if not user_id:
        try:
            user_id = global_variables.get_user_id()
        except Exception:
            user_id = None

    if not user_id:
        return set()

    url = f"https://beowulf.ironpoint.org/api/blackbox/user?user_id={user_id}"
    headers = {}
    if api_key.get('value'):
        headers['Authorization'] = api_key['value']

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            global_variables.log(f"Failed to fetch user kills: {resp.status_code}")
            return set()
        data = resp.json()
        # Diagnostic: log top-level response shape so we can adapt to API formats
        try:
            if isinstance(data, dict):
                keys = list(data.keys())
            else:
                keys = None
            # global_variables.log(f"API response type: {type(data).__name__}, top-level keys: {keys}")
        except Exception:
            pass
    except Exception as e:
        global_variables.log(f"Error fetching user kills from API: {e}")
        return set()

    kills = set()
    try:
        # support a few common response shapes
        if isinstance(data, dict):
            candidates = data.get('kills') or data.get('data') or data.get('results') or data.get('items') or []
        elif isinstance(data, list):
            candidates = data
        else:
            candidates = []

        # clear existing cache for fresh fetch
        try:
            api_kills_cache.clear()
        except Exception:
            pass

        # Diagnostics counters for debugging why items may be dropped
        non_dict_items = 0
        missing_time = 0
        missing_victim = 0
        added = 0

        for item in candidates:
            if not isinstance(item, dict):
                non_dict_items += 1
                continue

            # Victim(s) may be provided as a single field or as a list under 'victims'
            victims = []
            if 'victims' in item and isinstance(item.get('victims'), (list, tuple)):
                victims = item.get('victims')
            else:
                v = item.get('victim') or item.get('victim_name') or item.get('victimName')
                if v:
                    victims = [v]

            # Timestamp can appear under several keys; prefer 'timestamp'
            time_val = item.get('timestamp') or item.get('time') or item.get('kill_time') or item.get('timestamp')
            if not time_val:
                missing_time += 1
                # if no time value, skip adding for duplicate detection
                continue

            time_str = str(time_val).strip()
            if not victims:
                missing_victim += 1
            for victim in victims:
                if not victim:
                    missing_victim += 1
                    continue
                victim_str = str(victim).strip()
                key = (victim_str, time_str)
                kills.add(key)
                try:
                    api_kills_cache.add(key)
                except Exception:
                    # best-effort caching; don't break parsing for cache failures
                    pass
                added += 1
    except Exception as e:
        global_variables.log(f"Unexpected API response format when parsing kills: {e}")

    # Diagnostic summary about items processed / skipped
    try:
        try:
            candidates_len = len(candidates) if 'candidates' in locals() and candidates is not None else 'N/A'
        except Exception:
            candidates_len = 'N/A'
        # global_variables.log(f"API candidates: {candidates_len}, added: {added}, non-dict: {non_dict_items}, missing_time: {missing_time}, missing_victim: {missing_victim}")
        # Show a small sample of candidate items for inspection
        try:
            sample = candidates[:5] if isinstance(candidates, (list, tuple)) else None
            # if sample:
            #     global_variables.log(f"API candidates sample (first up to 5): {sample}")
        except Exception:
            pass
    except Exception:
        pass

    # global_variables.log(f"Fetched {len(kills)} existing kills for user_id {user_id}")
    # Debug: log the actual kills retrieved for easier troubleshooting.
    # try:
    #     if kills:
    #         # Convert to a stable list and limit the output length to avoid
    #         # spamming the UI if the set is large.
    #         kills_list = list(kills)
    #         display_count = 100
    #         if len(kills_list) > display_count:
    #             try:
    #                 global_variables.log(f"API kills (first {display_count} of {len(kills_list)}): {kills_list[:display_count]}")
    #             except Exception:
    #                 print(f"API kills (first {display_count} of {len(kills_list)}): {kills_list[:display_count]}")
    #         else:
    #             try:
    #                 global_variables.log(f"API kills: {kills_list}")
    #             except Exception:
    #                 print(f"API kills: {kills_list}")
    # except Exception:
    #     pass
    return kills


@global_variables.log_exceptions
def fetch_and_classify_api_kills_for_ui(user_id=None):
    """Fetch kills via API and prepare normalized records for the UI.

    - Normalizes each item to a dict with keys: victim, time, zone, weapon,
      game_mode, killers_ship, damage_type, source.
    - Splits into PU vs AC lists using available fields (game_mode or zone heuristics).
    - Stores results in global_variables (set_api_kills_data/set_api_kills_split).

    Returns (pu_list, ac_list).
    """
    # Try to use configured user id if not provided
    if not user_id:
        try:
            user_id = global_variables.get_user_id()
        except Exception:
            user_id = None

    # If no user_id, nothing to fetch
    if not user_id:
        global_variables.set_api_kills_data([])
        global_variables.set_api_kills_split([], [])
        return ([], [])

    # Ensure API key header ready
    try:
        key = global_variables.get_key()
        api_key['value'] = key
    except Exception:
        pass

    # Build request
    url = f"https://beowulf.ironpoint.org/api/blackbox/user?user_id={user_id}"
    headers = {}
    if api_key.get('value'):
        headers['Authorization'] = api_key['value']

    data = None
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            global_variables.log(f"Failed to fetch user kills: {resp.status_code}")
            global_variables.set_api_kills_data([])
            global_variables.set_api_kills_split([], [])
            return ([], [])
        data = resp.json()
    except Exception as e:
        global_variables.log(f"Error fetching user kills from API: {e}")
        global_variables.set_api_kills_data([])
        global_variables.set_api_kills_split([], [])
        return ([], [])

    # Determine candidate list
    if isinstance(data, dict):
        candidates = data.get('kills') or data.get('data') or data.get('results') or data.get('items') or []
    elif isinstance(data, list):
        candidates = data
    else:
        candidates = []

    normalized = []
    api_like_items = []  # for api_kills_all schema
    for item in candidates:
        if not isinstance(item, dict):
            continue
        # Extract with fallbacks
        victim = item.get('victim') or item.get('victim_name') or item.get('victimName')
        if not victim and isinstance(item.get('victims'), (list, tuple)) and item.get('victims'):
            try:
                victim = item.get('victims')[0]
            except Exception:
                victim = None
        time_val = item.get('timestamp') or item.get('time') or item.get('kill_time') or item.get('timestamp')
        zone = item.get('zone') or item.get('location') or item.get('map')
        weapon = item.get('weapon') or item.get('weapon_name')
        game_mode_val = item.get('game_mode') or item.get('mode') or item.get('gameMode')
        killers_ship = item.get('killers_ship') or item.get('ship') or item.get('ship_name')
        # ship_killed indicates FPS vs ship kill per API; keep raw value
        ship_killed = item.get('ship_killed') or item.get('shipKilled') or item.get('ship-killed')
        damage_type = item.get('damage_type') or item.get('damageType')
        # API-like fields commonly present; include with safe fallbacks
        id_val = item.get('id') or item.get('_id') or None
        user_id_val = item.get('user_id') or item.get('userId') or None
        ship_used = item.get('ship_used') or item.get('killers_ship') or item.get('ship') or None
        patch = item.get('patch') or None
        value = item.get('value') if isinstance(item.get('value'), int) else 0
        kill_count = item.get('kill_count') if isinstance(item.get('kill_count'), int) else 1
        victims_list = item.get('victims') if isinstance(item.get('victims'), list) else ([victim] if victim else [])

        rec = {
            'victim': str(victim).strip() if victim else None,
            'time': str(time_val).strip() if time_val else None,
            'zone': str(zone).strip() if zone else None,
            'weapon': str(weapon).strip() if weapon else None,
            'game_mode': str(game_mode_val).strip() if game_mode_val else None,
            'killers_ship': str(killers_ship).strip() if killers_ship else None,
            'damage_type': str(damage_type).strip() if damage_type else None,
            'ship_killed': str(ship_killed).strip() if ship_killed is not None else None,
            'source': 'api'
        }
        # Skip entries with neither victim nor time; insufficient for display
        if not rec['victim'] and not rec['time']:
            continue
        normalized.append(rec)

        # Build API-like record for combined list
        api_item = {
            'id': str(id_val) if id_val is not None else None,
            'user_id': str(user_id_val) if user_id_val is not None else None,
            'ship_used': str(ship_used).strip() if ship_used else None,
            'ship_killed': str(ship_killed).strip() if ship_killed is not None else None,
            'value': int(value) if isinstance(value, int) else 0,
            'kill_count': int(kill_count) if isinstance(kill_count, int) else 1,
            'victims': victims_list,
            'patch': str(patch) if patch is not None else None,
            'game_mode': str(game_mode_val).strip() if game_mode_val else None,
            'timestamp': str(time_val).strip() if time_val else None,
        }
        api_like_items.append(api_item)

    # Heuristic split: prefer explicit game_mode; fallback to zone/map cues
    pu_list, ac_list = [], []
    for rec in normalized:
        gm = (rec.get('game_mode') or '').lower()
        z = (rec.get('zone') or '').lower()
        is_ac = False
        # Common AC indicators
        if gm in ('arena_commander', 'ac', 'electronic_access', 'ea_starfighter', 'ea_duel', 'ea_freeflight', 'ea_vanduul_swarm'):
            is_ac = True
        elif 'arena' in z or 'dying star' in z or 'broken moon' in z or 'electronic access' in z:
            is_ac = True
        # Default to PU if not matched as AC
        if is_ac:
            ac_list.append(rec)
        else:
            pu_list.append(rec)

    # Store for UI
    global_variables.set_api_kills_data(normalized)
    global_variables.set_api_kills_split(pu_list, ac_list)
    # Also store the API-like combined list
    try:
        global_variables.set_api_kills_all(api_like_items)
    except Exception:
        pass
    return (pu_list, ac_list)


@global_variables.log_exceptions
def refresh_api_kills_cache(user_id=None):
    """Refresh the in-memory API kills cache.

    This should be called at startup and whenever the application needs an
    up-to-date list of kills from the remote API (for duplicate detection).
    The function returns the cached set of (victim, timestamp) tuples.
    """
    try:
        kills = get_user_kills_from_api(user_id)
        try:
            api_kills_cache.clear()
        except Exception:
            pass
        try:
            for k in kills:
                api_kills_cache.add(k)
        except Exception:
            pass

        # try:
        #     global_variables.log(f"API kills cache refreshed: {len(api_kills_cache)} entries")
        # except Exception:
        #     pass

        return api_kills_cache
    except Exception as e:
        try:
            global_variables.log(f"Failed to refresh API kills cache: {e}")
        except Exception:
            pass
        return set()

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
    'GRIN', 'TMBL', 'GAMA', 'GLSN'
]

global_game_mode = "Nothing"
global_active_ship = "N/A"
global_active_ship_id = "N/A"
global_player_geid = "N/A"

@global_variables.log_exceptions
def start_tail_log_thread(log_file_location, rsi_name):
    """Start the log tailing in a separate thread."""
    thread = threading.Thread(target=tail_log, args=(log_file_location, rsi_name))
    thread.daemon = True
    thread.start()

@global_variables.log_exceptions
def tail_log(log_file_location, rsi_name):
    """Read the log file and display events in the GUI.

    Uses `global_variables.log()` for thread-safe logging.
    """
    global global_game_mode, global_player_geid
    try:
        sc_log = open(log_file_location, "rb")
    except Exception as e:
        global_variables.log(f"Failed to open log file {log_file_location}: {e}")
        return

    global_variables.log("🗹 Log file found.")
    # logger.log("Enter key to establish Servitor connection...")

    # Read all lines to find out what game mode player is currently, in case they booted up late.
    # Don't upload kills, we don't want repeating last sessions kills incase they are actually available.
    # Read old lines as bytes and decode safely, logging any offending byte sequences
    def _decode_line_bytes(line_bytes, base_offset):
        try:
            return line_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            # e.start is the index within this line_bytes where decoding failed
            start = e.start
            end = e.end
            offending = line_bytes[start:end]
            file_pos = base_offset + start
            try:
                global_variables.log(
                    f"UnicodeDecodeError at byte pos {file_pos} (line offset {start}-{end}): {offending.hex()}"
                )
            except Exception:
                print(f"UnicodeDecodeError at byte pos {file_pos}: {offending.hex()}")
            # Return a replacement-decoded string so parsing can continue
            return line_bytes.decode("utf-8", errors="replace")

    lines = sc_log.readlines()
    base_offset = 0
    for bline in lines:
        line = _decode_line_bytes(bline, base_offset)
        base_offset += len(bline)
        read_log_line(line, rsi_name, False)

    # Main loop to monitor the log
    last_log_file_size = os.stat(log_file_location).st_size
    while True:
        where = sc_log.tell()
        bline = sc_log.readline()
        if not bline:
            time.sleep(1)
            sc_log.seek(where)
            if last_log_file_size > os.stat(log_file_location).st_size:
                sc_log.close()
                try:
                    sc_log = open(log_file_location, "rb")
                except Exception as e:
                    global_variables.log(f"Failed to reopen log file {log_file_location}: {e}")
                    time.sleep(1)
                    continue
                last_log_file_size = os.stat(log_file_location).st_size
        else:
            # decode the bytes and pass the resulting string to the parser
            line = _decode_line_bytes(bline, where)
            read_log_line(line, rsi_name, True)

@global_variables.log_exceptions
def read_existing_log(log_file_location, rsi_name):
    try:
        sc_log = open(log_file_location, "rb")
    except Exception as e:
        global_variables.log(f"Failed to open log file {log_file_location}: {e}")
        return

    def _decode_line_bytes(line_bytes, base_offset):
        try:
            return line_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            start = e.start
            end = e.end
            offending = line_bytes[start:end]
            file_pos = base_offset + start
            try:
                global_variables.log(
                    f"UnicodeDecodeError at byte pos {file_pos} (line offset {start}-{end}): {offending.hex()}"
                )
            except Exception:
                print(f"UnicodeDecodeError at byte pos {file_pos}: {offending.hex()}")
            return line_bytes.decode("utf-8", errors="replace")

    lines = sc_log.readlines()
    base_offset = 0
    for bline in lines:
        line = _decode_line_bytes(bline, base_offset)
        base_offset += len(bline)
        read_log_line(line, rsi_name, True)


@global_variables.log_exceptions
def parse_backup_logs(backup_dir, rsi_name, user_id=None, progress_callback=None, suppress_file_logs=False):
    """Parse all log files in the backup_dir without uploading kills.

    This will iterate all files in the directory and parse each as a log file.
    Kills are parsed but not sent to the server (upload_kills=False).

    Optional progress_callback(index, total, filepath) will be called before
    parsing each file so callers (e.g. a GUI) can show concise progress.

    Returns a tuple: (published_kills_count, duplicates_count)
    """
    try:
        if not backup_dir or not os.path.isdir(backup_dir):
            if not suppress_file_logs:
                global_variables.log(f"No backup directory found at: {backup_dir}")
            return (0, 0)

        files = [f for f in os.listdir(backup_dir) if os.path.isfile(os.path.join(backup_dir, f))]
        files.sort()
        total_files = len(files)
        if not suppress_file_logs:
            global_variables.log(f"Found {total_files} backup files in {backup_dir}")

        # Optionally fetch existing kills from the server to avoid duplicates
        existing_kills = set()
        # We'll also build a parsed-version of the API kills with datetimes
        existing_kills_parsed = []  # list of tuples (victim_lower, datetime or None, raw_time_str)
        # helper to parse ISO-like timestamps robustly (reusable for API and log timestamps)
        def _parse_ts(ts):
            if ts is None:
                return None
            try:
                s = str(ts).strip()
                # remove surrounding angle brackets or quotes
                if s.startswith('<') and s.endswith('>'):
                    s = s[1:-1].strip()
                # robustly strip any surrounding quotes
                s = s.strip().strip('"').strip("'")

                # Try common ISO formats; handle trailing Z (UTC)
                if s.endswith('Z'):
                    # Try with fractional seconds
                    try:
                        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                    except Exception:
                        try:
                            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        except Exception:
                            return None

                # Try fromisoformat which handles offsets like +00:00
                try:
                    dt = datetime.fromisoformat(s)
                    if dt.tzinfo is None:
                        # assume UTC when unspecified
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except Exception:
                    # Try without fractional seconds
                    try:
                        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                    except Exception:
                        return None
            except Exception:
                return None
        if user_id:
            try:
                existing_kills = get_user_kills_from_api(user_id)
                for ak in existing_kills:
                    try:
                        victim = str(ak[0]).strip()
                        raw_time = str(ak[1]).strip() if len(ak) > 1 else None
                        dt = _parse_ts(raw_time)
                        existing_kills_parsed.append((victim.lower(), dt, raw_time))
                    except Exception:
                        # best-effort: still keep the raw tuple if parsing failed
                        try:
                            existing_kills_parsed.append((str(ak[0]).strip().lower(), None, str(ak[1]) if len(ak) > 1 else None))
                        except Exception:
                            pass
            except Exception as e:
                if not suppress_file_logs:
                    global_variables.log(f"Error obtaining existing kills for duplicate check: {e}")

        # aggregate parsed kills from all backup files
        aggregated_kills = []
        duplicates_count = 0
        uploaded_count = 0
        uploaded_kills = []

        for idx, fname in enumerate(files):
            fpath = os.path.join(backup_dir, fname)
            # report concise progress to caller if provided
            if progress_callback:
                try:
                    progress_callback(idx + 1, total_files, fpath)
                except Exception:
                    # don't let progress callback failures stop parsing
                    pass

            if not suppress_file_logs:
                global_variables.log(f"Parsing backup file: {fpath}")

            # Reset vehicle destruction context at the start of each file so
            # location/coordinates don't leak between unrelated sessions/files.
            try:
                last_vehicle_context['zone'] = None
                last_vehicle_context['coordinates'] = None
                last_vehicle_context['time'] = None
                last_vehicle_context['killer'] = None
            except Exception:
                pass

            try:
                with open(fpath, "rb") as fh:
                    base_offset = 0
                    for bline in fh:
                        # decode line bytes safely
                        try:
                            line = bline.decode("utf-8")
                        except UnicodeDecodeError as e:
                            start = e.start
                            end = e.end
                            offending = bline[start:end]
                            file_pos = base_offset + start
                            if not suppress_file_logs:
                                global_variables.log(
                                    f"UnicodeDecodeError in backup {fname} at byte pos {file_pos} (offset {start}-{end}): {offending.hex()}"
                                )
                            line = bline.decode("utf-8", errors="replace")

                        base_offset += len(bline)
                        # parse but do not upload kills
                        try:
                            # allow read_log_line to update game/session state
                            read_log_line(line, rsi_name, False)
                            # Additionally, if this line is a kill line, parse it locally and collect result
                            if ("CActor::Kill" in line) and (not check_substring_list(line, ignore_kill_substrings)):
                                try:
                                    parsed = parse_kill_local(line, rsi_name, suppress_logs=suppress_file_logs)
                                    if parsed:
                                        # Duplicate check: look for API kills within 60 seconds of the backup kill
                                        try:
                                            parsed_victim = str(parsed.get('victim')).strip()
                                            parsed_time_str = str(parsed.get('time')).strip()
                                        except Exception:
                                            parsed_victim = None
                                            parsed_time_str = None

                                        is_dup = False
                                        # parse backup kill time into datetime (assume ISO or similar)
                                        parsed_dt = None
                                        try:
                                            parsed_dt = _parse_ts(parsed_time_str)
                                        except Exception:
                                            parsed_dt = None

                                        if parsed_victim:
                                            pv_lower = parsed_victim.lower()
                                            # check each existing API kill for victim match and timestamp window
                                            for (ak_victim_lower, ak_dt, ak_raw) in existing_kills_parsed:
                                                try:
                                                    if ak_victim_lower != pv_lower:
                                                        continue
                                                    # if API kill has no parsed dt, fall back to raw string equality of time
                                                    if ak_dt is None or parsed_dt is None:
                                                        # fall back to exact raw time string compare
                                                        if ak_raw and parsed_time_str and ak_raw == parsed_time_str:
                                                            is_dup = True
                                                            break
                                                        else:
                                                            continue

                                                    # compute delta = api_time - backup_time (seconds)
                                                    delta = (ak_dt - parsed_dt).total_seconds()
                                                    # consider duplicates where API kill is within +/-60 seconds of backup kill
                                                    if abs(delta) <= 60:
                                                        is_dup = True
                                                        break
                                                except Exception:
                                                    continue

                                        if is_dup:
                                            duplicates_count += 1
                                            if not suppress_file_logs:
                                                global_variables.log(f"Skipping already-logged kill from backup (matched API within 60s): {parsed_victim} at {parsed_time_str}")
                                        else:
                                            # non-duplicate: attempt to publish like parse_kill_line would
                                            try:
                                                # send_kill_to_api expects the JSON-shaped data similar to parse_kill_line
                                                json_data = {
                                                    'player': rsi_name,
                                                    'victim': parsed.get('victim'),
                                                    'time': parsed.get('time'),
                                                    'zone': parsed.get('zone'),
                                                        'location': last_vehicle_context.get('zone'),
                                                        'coordinates': last_vehicle_context.get('coordinates'),
                                                    'weapon': parsed.get('weapon'),
                                                    'rsi_profile': f"https://robertsspaceindustries.com/citizens/{parsed.get('victim')}",
                                                    'game_mode': global_game_mode,
                                                    'client_ver': local_version,
                                                    'killers_ship': global_active_ship,
                                                    'damage_type': parsed.get('damage_type')
                                                }
                                                sent = send_kill_to_api(json_data, suppress_logs=suppress_file_logs)
                                                if sent:
                                                    uploaded_count += 1
                                                    try:
                                                        uploaded_kills.append(parsed)
                                                    except Exception:
                                                        pass
                                                else:
                                                    # If sending failed, still keep local aggregated record for reporting
                                                    aggregated_kills.append(parsed)
                                            except Exception:
                                                aggregated_kills.append(parsed)
                                except Exception as e:
                                    if not suppress_file_logs:
                                        global_variables.log(f"Error parsing kill line in {fname}: {e}")
                        except Exception as e:
                            if not suppress_file_logs:
                                global_variables.log(f"Error parsing line in {fname}: {e}")
            except Exception as e:
                if not suppress_file_logs:
                    global_variables.log(f"Failed to parse backup file {fpath}: {e}")

    except Exception as e:
        global_variables.log(f"Error in parse_backup_logs: {e}")
        return (0, 0)

    # After successfully parsing all files, publish a summary of kills
    try:
        # Combine uploaded_kills and aggregated_kills for a full summary
        all_kills_for_summary = []
        try:
            all_kills_for_summary.extend(uploaded_kills)
        except Exception:
            pass
        try:
            all_kills_for_summary.extend(aggregated_kills)
        except Exception:
            pass

        if all_kills_for_summary:
            # aggregate by victim
            summary = {}
            for k in all_kills_for_summary:
                victim = k.get('victim')
                weapon = k.get('weapon')
                damage = k.get('damage_type')
                summary.setdefault(victim, []).append((weapon, damage))

            global_variables.log("\nBackup parse summary:")
            total_kills = 0
            for victim, details in summary.items():
                total_kills += len(details)
                # count weapons/damage occurrences
                counts = {}
                for w, d in details:
                    key = f"{w} ({d})"
                    counts[key] = counts.get(key, 0) + 1
                weapons_summary = ", ".join([f"{k}: {v}" for k, v in counts.items()])
                global_variables.log(f"{victim}: {len(details)} kills — {weapons_summary}")

            global_variables.log(f"Total kills parsed from backups: {total_kills} (uploaded: {uploaded_count}, failed uploads: {len(aggregated_kills)})")
        else:
            global_variables.log("No kills found in backup logs.")
    except Exception as e:
        global_variables.log(f"Error generating backup summary: {e}")

    # Return summary counts: (published_count, duplicates_count)
    try:
        return (uploaded_count, duplicates_count)
    except Exception:
        return (0, duplicates_count)

# Trigger kill event
@global_variables.log_exceptions
def parse_kill_line(line, target_name):
    key = global_variables.get_key()
    # use global_variables.log for logging
    api_key['value'] = key
    global_variables.log(f"Current API Key: {api_key['value']}")

    if not check_exclusion_scenarios(line):
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
        global_variables.log("You DIED.")
        return

    event_message = f"You have killed {killed},"
    global_variables.log(event_message)
    json_data = {
        'player': target_name,
        'victim': killed,
        'time': kill_time,
        'zone': killed_zone,
        'location': last_vehicle_context.get('zone'),
        'coordinates': last_vehicle_context.get('coordinates'),
        'weapon': weapon,
        'rsi_profile': f"https://robertsspaceindustries.com/citizens/{killed}",
        'game_mode': global_game_mode,
        'client_ver': "7.0",
        'killers_ship': global_active_ship,
        'damage_type': damage_type
    }

    # After recording to combined list, refresh UI lists from all_kills to avoid duplicates
    try:
        app = global_variables.get_app()
        refs = global_variables.get_main_tab_refs()
        refresh = refs.get('refresh_kill_columns')
        if app is not None and callable(refresh):
            try:
                app.after(0, refresh)
            except Exception:
                refresh()
        elif callable(refresh):
            refresh()
    except Exception:
        pass

    # Publish to API (network)
    try:
        publish_kill(json_data, suppress_logs=False)
    except Exception as e:
        global_variables.log(f"Error sending kill event: {e}")

    # Append to combined in-memory list (API-like schema)
    try:
        existing = []
        try:
            existing = list(global_variables.get_api_kills_all())
        except Exception:
            existing = []
        # Map live kill into the API-like schema
        # Note: id and user_id may be unknown locally; leave as None.
        # Derive ship_killed as 'FPS' if weapon/damage suggests FPS, else None to imply ship-based.
        dt = (damage_type or '').lower()
        fps_markers = ('bullet', 'melee', 'explosion', 'grenade', 'bleed', 'laser', 'railgun')
        is_fps = any(m in dt for m in fps_markers) and (not (global_active_ship or '').strip() or (global_active_ship or '').strip().upper() == 'N/A')
        api_like = {
            'id': None,
            'user_id': None,
            'ship_used': global_active_ship if global_active_ship and global_active_ship != 'N/A' else None,
            'ship_killed': 'FPS' if is_fps else None,
            'value': 0,
            'kill_count': 1,
            'victims': [killed] if killed else [],
            'patch': None,
            'game_mode': global_game_mode,
            'timestamp': kill_time,
        }
        existing.append(api_like)
        global_variables.set_api_kills_all(existing)
    except Exception:
        pass


@global_variables.log_exceptions
def parse_kill_local(line, target_name, suppress_logs=False):
    """Parse a kill line and log the parsed kill locally without attempting to upload."""
    try:
        split_line = line.split(' ')
        kill_time = split_line[0].strip("'")
        killed = split_line[5].strip("'")
        killed_zone = split_line[9].strip("'")
        killer = split_line[12].strip("'")
        weapon = split_line[15].strip("'")
        damage_type = split_line[21].strip("'")

        if killed == killer or killer.lower() == "unknown" or killed == target_name:
            if not suppress_logs:
                global_variables.log("You DIED.")
            return

        event_message = f"[BACKUP] You have killed {killed} at {kill_time} in {killed_zone} using {weapon} (damage: {damage_type})"
        if not suppress_logs:
            global_variables.log(event_message)

        # Also present a compact JSON-like summary for debugging/inspection
        json_data = {
            'player': target_name,
            'victim': killed,
            'time': kill_time,
            'zone': killed_zone,
            'location': last_vehicle_context.get('zone'),
            'coordinates': last_vehicle_context.get('coordinates'),
            'weapon': weapon,
            'rsi_profile': f"https://robertsspaceindustries.com/citizens/{killed}",
            'game_mode': global_game_mode,
            'client_ver': "7.0",
            'killers_ship': global_active_ship,
            'damage_type': damage_type,
            'source': 'backup'
        }
        try:
            if not suppress_logs:
                global_variables.log(f"Parsed kill (backup): {json.dumps(json_data)}")
        except Exception:
            if not suppress_logs:
                global_variables.log(str(json_data))
        return json_data
    except Exception as e:
        global_variables.log(f"parse_kill_local error: {e}")
        return None


@global_variables.log_exceptions
def send_kill_to_api(json_data, suppress_logs=False):
    """Send a kill JSON payload to the API. Returns True on successful POST (200/201)."""
    # Delegate to the central publishing helper
    try:
        return publish_kill(json_data, suppress_logs=suppress_logs)
    except Exception:
        return False


@global_variables.log_exceptions
def publish_kill(json_data, suppress_logs=False):
    """Centralized publish function used by live and backup flows.

    Returns True on success (HTTP 200/201) and False otherwise.
    """
    try:
        key = global_variables.get_key()
    except Exception:
        key = None

    api_key['value'] = key
    if not api_key.get('value'):
        if not suppress_logs:
            global_variables.log("Kill event will not be sent. Enter valid key to establish connection with Servitor...")
        return False

    headers = {
        'content-type': 'application/json',
        'Authorization': api_key['value'] if api_key.get('value') else ""
    }

    try:
        response = requests.post(
            "https://beowulf.ironpoint.org/api/reportkill",
            headers=headers,
            data=json.dumps(json_data),
            timeout=15
        )
        if response.status_code in (200, 201):
            if not suppress_logs:
                global_variables.log("Kill logged.")
            return True
        else:
            if not suppress_logs:
                global_variables.log("Relaunch BeowulfHunter and reconnect with a new Key.")
            return False
    except requests.exceptions.RequestException as e:
        if not suppress_logs:
            global_variables.log(f"Error sending kill event: {e}")
        return False

@global_variables.log_exceptions
def check_substring_list(line, substring_list):
    """
    Check if any substring from the list is present in the given line.
    """
    for substring in substring_list:
        if substring.lower() in line.lower():
            return True
    return False

@global_variables.log_exceptions
def check_exclusion_scenarios(line):
    global global_game_mode
    if global_game_mode == "EA_FreeFlight" and -1 != line.find("Crash"):
        global_variables.log("Probably a ship reset, ignoring kill!")
        return False
    return True

@global_variables.log_exceptions
def find_rsi_geid(log_file_location):
    global global_player_geid
    acct_kw = "AccountLoginCharacterStatus_Character"
    try:
        sc_log = open(log_file_location, "rb")
    except Exception as e:
        global_variables.log(f"Failed to open log file {log_file_location}: {e}")
        return

    def _decode_line_bytes(line_bytes, base_offset):
        try:
            return line_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            start = e.start
            end = e.end
            offending = line_bytes[start:end]
            file_pos = base_offset + start
            try:
                global_variables.log(
                    f"UnicodeDecodeError at byte pos {file_pos} (line offset {start}-{end}): {offending.hex()}"
                )
            except Exception:
                print(f"UnicodeDecodeError at byte pos {file_pos}: {offending.hex()}")
            return line_bytes.decode("utf-8", errors="replace")

    lines = sc_log.readlines()
    for line in lines:
        # line is bytes; decode safely preserving offsets
        # we cannot easily track exact file offsets here, so pass base_offset=0
        text_line = _decode_line_bytes(line, 0)
        if -1 != text_line.find(acct_kw):
            global_player_geid = text_line.split(' ')[11]
            global_variables.log("Player geid: " + global_player_geid)
            return

@global_variables.log_exceptions
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

@global_variables.log_exceptions
def read_log_line(line, rsi_name, upload_kills):
    if -1 != line.find("<Context Establisher Done>"):
        set_game_mode(line)
    elif -1 != line.find(rsi_name):
        if -1 != line.find("OnEntityEnterZone"):
            set_player_zone(line)
        if -1 != line.find("CActor::Kill") and not check_substring_list(line, ignore_kill_substrings) and upload_kills:
            parse_kill_line(line, rsi_name)
    # Capture Vehicle Destruction context whenever present; pass rsi_name so we can filter to local player
    if -1 != line.find("<Vehicle Destruction>"):
        update_vehicle_destruction_context(line, rsi_name)
    elif -1 != line.find("CPlayerShipRespawnManager::OnVehicleSpawned") and (
            "SC_Default" != global_game_mode) and (-1 != line.find(global_player_geid)):
        set_ac_ship(line)
    elif ((-1 != line.find("<Vehicle Destruction>")) or (
            -1 != line.find("<local client>: Entering control state dead"))) and (
            -1 != line.find(global_active_ship_id)):
        destroy_player_zone(line)


@global_variables.log_exceptions
def destroy_player_zone(line):
    global global_active_ship
    global global_active_ship_id
    if ("N/A" != global_active_ship) or ("N/A" != global_active_ship_id):
        global_variables.log(f"Ship Destroyed: {global_active_ship} with ID: {global_active_ship_id}")
        global_active_ship = "N/A"
        global_active_ship_id = "N/A"
    # Reset any stale vehicle destruction context when our ship is destroyed
    try:
        last_vehicle_context['zone'] = None
        last_vehicle_context['coordinates'] = None
        last_vehicle_context['time'] = None
        last_vehicle_context['killer'] = None
    except Exception:
        pass

@global_variables.log_exceptions
def set_ac_ship(line):
    global global_active_ship
    global_active_ship = line.split(' ')[5][1:-1]
    global_variables.log(f"Player has entered ship: {global_active_ship}")
    # Reset VD context on new ship spawn to avoid mixing state across ships
    try:
        last_vehicle_context['zone'] = None
        last_vehicle_context['coordinates'] = None
        last_vehicle_context['time'] = None
        last_vehicle_context['killer'] = None
    except Exception:
        pass

@global_variables.log_exceptions
def set_player_zone(line):
    global global_active_ship
    global global_active_ship_id
    line_index = line.index("-> Entity ") + len("-> Entity ")
    if 0 == line_index:
        global_variables.log(f"Active Zone Change: {global_active_ship}")
        global_active_ship = "N/A"
        return
    potential_zone = line[line_index:].split(' ')[0]
    potential_zone = potential_zone[1:-1]
    for x in global_ship_list:
        if potential_zone.startswith(x):
            global_active_ship = potential_zone[:potential_zone.rindex('_')]
            global_active_ship_id = potential_zone[potential_zone.rindex('_') + 1:]
            global_variables.log(f"Active Zone Change: {global_active_ship} with ID: {global_active_ship_id}")
            return
        
