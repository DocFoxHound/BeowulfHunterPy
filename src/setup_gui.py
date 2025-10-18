import os
import requests
import webbrowser
import tkinter as tk
import tkinter.font as tkFont
from tkinter import ttk
from tkinter import scrolledtext
import sys
from packaging import version
from PIL import Image, ImageTk
from config import set_sc_log_location, get_player_name, find_rsi_handle, is_game_running
from keys import validate_api_key, save_api_key, load_existing_key
import backup_loader
import global_variables
from filelock import FileLock, Timeout
import tempfile
import threading
import time
import parser
from tabs import main_tab as main_tab_builder
from tabs import piracy_tab as piracy_tab_builder
from tabs import dogfighting_tab as dogfighting_tab_builder
from tabs import log_tab as log_tab_builder
from controllers.key_controller import KeyController
from controllers.game_controller import GameController
from theme import BUTTON_STYLE, apply_ttk_styles

local_version = "7.0"  # Local app version used for update check

@global_variables.log_exceptions
def setup_gui(game_running):
    app = tk.Tk()
    app.title("BeowulfHunter")
    app.geometry("650x400")
    app.resizable(False, False)
    app.configure(bg="#1a1a1a")
    # Expose BUTTON_STYLE for other modules (e.g., controllers)
    setattr(app, 'BUTTON_STYLE', BUTTON_STYLE)

    # Set the icon
    try:
        icon_path = resource_path("beo.ico")
        if os.path.exists(icon_path):
            app.iconbitmap(icon_path)
    except Exception as e:
        global_variables.log(f"Error setting icon: {e}")

    # Prepare resources that will be used inside the Main tab
    try:
        banner_path = resource_path("beohunter.png")
    except Exception:
        banner_path = None

    # Check for Updates
    update_message = check_for_updates()

    # No separate header; tabs will occupy the full window with tabs at the top
    header_frame = None
    header_controls_placeholder = None
    setattr(app, 'header_frame', header_frame)
    setattr(app, 'header_controls_placeholder', header_controls_placeholder)

    # Configure ttk styles via theme module
    try:
        apply_ttk_styles(app)
    except Exception:
        pass

    # Tabs: Main, Piracy, Dogfighting, Log
    notebook = ttk.Notebook(app, style='Dark.TNotebook')
    try:
        notebook.configure(takefocus=0)
    except Exception:
        pass
    try:
        notebook.configure(borderwidth=0, padding=0, highlightthickness=0, relief='flat')
    except Exception:
        pass
    main_tab = ttk.Frame(notebook, style='Dark.TFrame')
    piracy_tab = ttk.Frame(notebook, style='Dark.TFrame')
    dogfighting_tab = ttk.Frame(notebook, style='Dark.TFrame')
    log_tab = ttk.Frame(notebook, style='Dark.TFrame')

    notebook.add(main_tab, text="Main")
    notebook.add(piracy_tab, text="Piracy")
    notebook.add(dogfighting_tab, text="Dogfighting")
    notebook.add(log_tab, text="Log")
    # Make the notebook fill the entire application window
    notebook.pack(padx=0, pady=0, fill=tk.BOTH, expand=True)

    # Store references for later use
    setattr(app, 'notebook', notebook)
    setattr(app, 'tabs', {
        'main': main_tab,
        'piracy': piracy_tab,
        'dogfighting': dogfighting_tab,
        'log': log_tab,
    })

    # Build each tab's contents via modular builders
    main_refs = main_tab_builder.build(main_tab, app, banner_path=banner_path, update_message=update_message, on_update_click=open_github)
    setattr(app, 'main_tab_refs', main_refs)
    try:
        global_variables.set_app(app)
        global_variables.set_main_tab_refs(main_refs)
    except Exception:
        pass
    log_refs = log_tab_builder.build(log_tab, app)
    piracy_refs = piracy_tab_builder.build(piracy_tab)
    dogfighting_refs = dogfighting_tab_builder.build(dogfighting_tab)
    setattr(app, 'piracy_tab_refs', piracy_refs)
    setattr(app, 'dogfighting_tab_refs', dogfighting_refs)

    # Make the logger reference easily available
    text_area = log_refs.get('log_text_area')
    if text_area is not None:
        global_variables.set_logger(text_area)

    # Placeholders are now added by the builders

    # Always initialize the full GUI immediately; we'll show a live game
    # status indicator (red/green) that updates as the game starts.
    initialize_game_gui(app)

    # (Graphs tab removed; no refresh binding needed)

    # No footer; notebook uses entire window

    # Lock the window size after layout so subsequent font changes inside
    # the text widget don't cause the toplevel to request a new geometry.
    try:
        app.update_idletasks()
        w = app.winfo_width()
        h = app.winfo_height()
        # Prevent the window from resizing due to internal widget requests
        app.minsize(w, h)
        app.maxsize(w, h)
    except Exception:
        # If anything fails here, don't block GUI startup; it's non-fatal.
        pass

    return app, None


    


@global_variables.log_exceptions
def on_game_relaunch(app, message_label=None):
    """Update the GUI when the game is detected as running."""
    # If a waiting label was provided, remove it; otherwise nothing to destroy
    try:
        if message_label is not None:
            message_label.destroy()
    except Exception:
        pass
    initialize_game_gui(app)


@global_variables.log_exceptions
def initialize_game_gui(app):
    # Try to set log file location if available, then discover RSI handle.
    # Only attempt when a valid path is returned to avoid None errors.
    try:
        potential_log = set_sc_log_location()
        if potential_log:
            global_variables.set_log_file_location(potential_log)
            try:
                rh = find_rsi_handle(potential_log)
                if rh:
                    global_variables.set_rsi_handle(rh)
            except Exception:
                # Will be logged by decorator; safe to continue without handle
                pass
    except Exception:
        pass
    # Snapshot current values; individual actions should fetch fresh values as needed
    log_file_location = global_variables.get_log_file_location()
    rsi_handle = global_variables.get_rsi_handle()

    # Graphs are now shown via a popup from the Dogfighting tab; Graphs tab remains as a notice only.

    # No header; indicator will render inside banner on Main tab via GameController

    # Game status indicator and monitor
    banner_canvas = getattr(app, 'banner_canvas', None)
    game_controller = GameController(app, banner_canvas)
    game_controller.setup_indicator()

    # API Key Input (now provided by main tab builder)
    tabs = getattr(app, 'tabs', {})
    main_tab_widget = tabs.get('main', app)
    _main_refs = getattr(app, 'main_tab_refs', {})
    key_section = _main_refs.get('key_section')
    key_entry = _main_refs.get('key_entry')
    # Status label removed; rely on banner key indicator instead

    # Ensure a logger/text_area exists; if setup_gui already created it, reuse it.
    existing_logger = global_variables.get_logger()
    if existing_logger is None and text_area is not None:
        global_variables.set_logger(text_area)
    elif existing_logger is not None:
        text_area = existing_logger.text_widget

    # Controller for key activation/validation and backup controls
    key_controller = KeyController(app, key_section, key_entry, text_area)

    # Automatically validate the saved key
    key_controller.validate_saved_key()

    # The 'Load Previous Logs' button is created by the Log tab builder; no need to
    # recreate it here.

    # Wire up the Activate button created in the main tab builder
    try:
        activate_button = _main_refs.get('activate_button')
        if activate_button is not None:
            activate_button.configure(command=key_controller.activate_key)
    except Exception:
        pass

    # If the key section is visible (no/invalid key), ensure kill columns are hidden
    try:
        if key_section.winfo_ismapped():
            refs = getattr(app, 'main_tab_refs', {})
            hide_cols = refs.get('hide_kill_columns')
            if callable(hide_cols):
                hide_cols()
    except Exception:
        pass

    # Ensure the main window size is fixed after layout so changing the
    # text widget font size doesn't cause the toplevel to resize.
    try:
        app.update_idletasks()
        w = app.winfo_width()
        h = app.winfo_height()
        app.minsize(w, h)
        app.maxsize(w, h)
    except Exception:
        pass


    # Old monitoring helpers removed; logic lives in controllers.game_controller


@global_variables.log_exceptions
def resource_path(relative_path):
    """ Get the absolute path to the resource (works for PyInstaller .exe). """
    try:
        base_path = sys._MEIPASS  
    except AttributeError:
        base_path = os.path.abspath(".")  
    return os.path.join(base_path, relative_path)

@global_variables.log_exceptions
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
            global_variables.log(f"GitHub API error: {response.status_code}")
    except Exception as e:
        global_variables.log(f"Error checking for updates: {e}")
    return None

@global_variables.log_exceptions
def open_github(event, update_message):
    try:
        url = update_message.split("Download it here: ")[-1]
        webbrowser.open(url)
    except Exception as e:
        global_variables.log(f"Error opening GitHub link: {e}")