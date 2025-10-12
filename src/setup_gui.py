import os
import requests
import webbrowser
import tkinter as tk
import tkinter.font as tkFont
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
import graphs

local_version = "7.0"  # You could pass this as a parameter if needed

# Shared button style constant so multiple functions can reuse it
BUTTON_STYLE = {
    "bg": "#0f0f0f",
    "fg": "#ff5555",
    "activebackground": "#330000",
    "activeforeground": "#ffffff",
    "relief": "ridge",
    "bd": 2,
    "font": ("Times New Roman", 12)
}

@global_variables.log_exceptions
def setup_gui(game_running):
    app = tk.Tk()
    app.title("BeowulfHunter")
    app.geometry("650x900")
    app.resizable(False, False)
    app.configure(bg="#1a1a1a")

    # Set the icon
    try:
        icon_path = resource_path("beo.ico")
        if os.path.exists(icon_path):
            app.iconbitmap(icon_path)
    except Exception as e:
        global_variables.log(f"Error setting icon: {e}")

    # Add Banner
    try:
        banner_path = resource_path("beohunter.png")
        original_image = Image.open(banner_path)
        resized_image = original_image.resize((480, 150), Image.Resampling.LANCZOS)
        banner_image = ImageTk.PhotoImage(resized_image)
        banner_label = tk.Label(app, image=banner_image, bg="#1a1a1a")
        banner_label.image = banner_image
        banner_label.pack(pady=(0, 10))
    except Exception as e:
        global_variables.log(f"Error loading banner image: {e}")

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

    # Top header: keep key entry, API status, and persistent controls here so
    # they are never hidden by the log text area.
    header_frame = tk.Frame(app, bg="#1a1a1a")
    header_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 0))

    # Placeholder for right-side header controls (Load Previous Logs etc.)
    header_controls_placeholder = tk.Frame(header_frame, bg="#1a1a1a")
    header_controls_placeholder.pack(side=tk.RIGHT)

    # Attach to app so other functions can find the header and placeholder
    # even when they run later.
    setattr(app, 'header_frame', header_frame)
    setattr(app, 'header_controls_placeholder', header_controls_placeholder)

    # If the game is not running, show a waiting message
    # Create the log display early so it is visible while we wait for the game
    # We'll place the text area and a right-side control column in a container
    log_container = tk.Frame(app, bg="#1a1a1a")
    # Pack the log container at the bottom so key input and status widgets
    # (created later) stay above it and remain visible.
    # Compute a pixel width/height for the container based on the initial
    # text widget font so subsequent font changes don't resize the box.
    initial_font = ("Times New Roman", 12)
    try:
        sample_font = tkFont.Font(font=initial_font)
        char_w = sample_font.measure('0') or 8
        line_h = sample_font.metrics('linespace') or 15
        px_width = int(80 * char_w + 24)  # 80 chars + scrollbar/padding
        px_height = int(20 * line_h + 12)
        log_container.config(width=px_width, height=px_height)
        # Prevent children from forcing the container to resize
        log_container.pack_propagate(False)
    except Exception:
        # Fallback to normal packing if any measurement fails
        pass

    # Attach log_container to app so other initializers can reuse it
    setattr(app, 'log_container', log_container)
    # Let the log container expand to fill available central space so the
    # header is directly above it and the footer remains at the very bottom.
    log_container.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
    # Allow children to request size changes so content sits naturally.
    try:
        log_container.pack_propagate(True)
    except Exception:
        pass

    # Top: make the text area span the full width so logs take the primary space.
    top_text_container = tk.Frame(log_container, bg="#1a1a1a")
    # Try to make the top text area a fixed height (px_height - bottom_h)
    try:
        bottom_h = int((px_height // 2) if 'px_height' in locals() else 320)
        top_h = max(80, int(px_height - bottom_h))
        top_text_container.config(height=top_h)
        top_text_container.pack_propagate(False)
        top_text_container.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
    except Exception:
        top_text_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    text_area = scrolledtext.ScrolledText(
        top_text_container,
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
        font=("Times New Roman", 12)
    )
    # Fill the top area completely with the text widget
    text_area.place(x=0, y=0, relwidth=1, relheight=1)

    

    # Persistent font controls — place these in the header placeholder so
    # they remain visible and do not consume space beside the text area.
    # Use the header placeholder created above so initialize_game_gui can
    # reuse the same controls and avoid duplicates.
    parent_for_controls = getattr(app, 'header_controls_placeholder', None)
    if parent_for_controls is None:
        parent_for_controls = header_frame

    # Only create the control frame/buttons if they don't already exist on
    # the app object (prevents duplicates when initialize_game_gui runs
    # later).
    if getattr(app, 'inc_btn', None) is None and getattr(app, 'font_control_frame', None) is None:
        # Create a slightly wider control container and place it in the
        # header placeholder. Use grid for the buttons so both are visible
        # even in tight header layouts.
        font_control_frame = tk.Frame(parent_for_controls, bg="#1a1a1a")
        font_control_frame.config(width=72)
        font_control_frame.pack_propagate(False)
        font_control_frame.pack(side=tk.RIGHT, padx=(8, 0), fill=tk.Y)
        setattr(app, 'font_control_frame', font_control_frame)

        def _change_font(delta):
            try:
                f = tkFont.Font(font=text_area['font'])
                current_size = f.actual('size')
                new_size = max(6, int(current_size) + delta)
                new_font = (f.actual('family'), new_size)
                text_area.config(font=new_font)
            except Exception as e:
                global_variables.log(f"Error changing font size: {e}")

        def increase_font():
            _change_font(1)

        def decrease_font():
            _change_font(-1)

        inc_btn = tk.Button(font_control_frame, text="A+", command=increase_font, **BUTTON_STYLE)
        dec_btn = tk.Button(font_control_frame, text="A-", command=decrease_font, **BUTTON_STYLE)
        # Use grid so both buttons share the horizontal space and remain visible.
        font_control_frame.columnconfigure(0, weight=1)
        font_control_frame.columnconfigure(1, weight=1)
        inc_btn.grid(row=0, column=0, padx=(2, 2), pady=4)
        dec_btn.grid(row=0, column=1, padx=(2, 2), pady=4)
        setattr(app, 'inc_btn', inc_btn)
        setattr(app, 'dec_btn', dec_btn)

        # Add a 'Show Kill Graph' button next to the font controls so it's
        # always visible in the header area. Guard against missing
        # matplotlib by letting graphs.show_kill_graph handle that.
        try:
            def _header_show_graph():
                try:
                    gw = getattr(app, 'graph_widget', None)
                    if gw is not None:
                        try:
                            gw.refresh()
                        except Exception:
                            global_variables.log("Failed to refresh embedded graph.")
                    else:
                        global_variables.log("Graph not available in this layout.")
                except Exception:
                    global_variables.log("Error invoking graph refresh.")

            graph_btn = tk.Button(font_control_frame, text="Graph", command=_header_show_graph, **BUTTON_STYLE)
            graph_btn.grid(row=0, column=2, padx=(6, 2), pady=4)
            setattr(app, 'graph_btn', graph_btn)
        except Exception:
            # Non-fatal: graph feature is optional.
            pass

    # Font controls created above; no duplicate creation here.

    global_variables.set_logger(text_area)  # Make the logger available immediately

    # Use module-level BUTTON_STYLE so other functions can reuse it

    # Note: 'Load Previous Logs' controls are created inside initialize_game_gui
    # after the user has a validated key. This prevents the button from being
    # visible while the API key is not validated.

    if not game_running:
        # Log the waiting message into the text box instead of showing a separate label
        global_variables.log("Waiting for Star Citizen to Launch.")

        # Start a background thread to monitor the game's status
        def monitor_game_status():
            while True:
                if is_game_running():
                    # Update the GUI when the game starts
                    app.after(0, on_game_relaunch, app, None)
                    break
                time.sleep(1)  # Check every second

        threading.Thread(target=monitor_game_status, daemon=True).start()

    else:
        # Initialize the GUI for when the game is already running
        initialize_game_gui(app)

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
    # Set log file location and try to discover RSI handle/player name; failures will be logged
    global_variables.set_log_file_location(set_sc_log_location())  # Set the log file location in global variables
    log_file_location = global_variables.get_log_file_location()
    try:
        global_variables.set_rsi_handle(find_rsi_handle(log_file_location))  # Retrieve the player name
    except Exception:
        # find_rsi_handle will be logged by its decorator if it fails
        pass
    rsi_handle = global_variables.get_rsi_handle()
    player_name = None
    try:
        if log_file_location:
            player_name = get_player_name(log_file_location)
    except Exception:
        pass

    # Ensure a fixed-size log_container exists so the text area remains a
    # static size regardless of the amount of text it contains. If
    # `setup_gui` already created it, reuse that; otherwise create one here
    # using the same measurement logic so behavior is consistent.
    existing_log = getattr(app, 'log_container', None)
    if existing_log is None:
        log_container = tk.Frame(app, bg="#1a1a1a")
        # Try to compute a pixel size from the baseline font metrics
        initial_font = ("Times New Roman", 12)
        try:
            sample_font = tkFont.Font(font=initial_font)
            char_w = sample_font.measure('0') or 8
            line_h = sample_font.metrics('linespace') or 15
            px_width = int(80 * char_w + 24)  # 80 chars + scrollbar/padding
            px_height = int(20 * line_h + 12)
            log_container.config(width=px_width, height=px_height)
            log_container.pack_propagate(False)
        except Exception:
            # If measurement fails, fall back to a reasonable fixed size
            try:
                log_container.config(width=650 - 40, height=600)
                log_container.pack_propagate(False)
            except Exception:
                pass
        setattr(app, 'log_container', log_container)
    else:
        log_container = existing_log
    # Pack the log_container to expand in the middle area between header
    # and footer so layout is natural and no large gaps appear.
    log_container.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # Create a top text area that spans full width, and a bottom row
    # with a left graph (1/4 width) and a right placeholder for details.
    try:
        # Top text area container
        top_text_container = tk.Frame(log_container, bg="#1a1a1a")
        # If px_height was computed, size the top area to px_height - bottom_h
        try:
            bottom_h = int((px_height // 2) if 'px_height' in locals() else 320)
            top_h = max(80, int(px_height - bottom_h))
            top_text_container.config(height=top_h)
            top_text_container.pack_propagate(False)
            top_text_container.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        except Exception:
            top_text_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        setattr(app, 'top_text_container', top_text_container)

        # Bottom frame sized to a portion of the log_container
        bottom_frame = tk.Frame(log_container, bg="#1a1a1a")
        try:
            bottom_h = int((px_height // 2) if 'px_height' in locals() else 320)
            bottom_frame.config(height=bottom_h)
            bottom_frame.pack_propagate(False)
        except Exception:
            pass
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        graph_frame = tk.Frame(bottom_frame, bg="#1a1a1a")
        try:
            graph_w = int((px_width // 4) if 'px_width' in locals() else 360)
            graph_frame.config(width=graph_w)
            graph_frame.pack_propagate(False)
        except Exception:
            pass
        graph_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        placeholder_frame = tk.Frame(bottom_frame, bg="#2a2a2a")
        placeholder_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        placeholder_label = tk.Label(placeholder_frame, text="Details placeholder", fg="#bcbcd8", bg="#2a2a2a", font=("Times New Roman", 11))
        placeholder_label.pack(padx=6, pady=6, anchor='nw')

        # instantiate the graph widget in the bottom-left quarter
        try:
            setattr(app, 'graph_widget', graphs.GraphWidget(graph_frame, width=graph_w, height=bottom_h))
        except Exception:
            pass
    except Exception:
        pass
        # Allow children to control sizing so the footer stays at the bottom
        # and the top content sits directly under the header.
        try:
            log_container.pack_propagate(True)
        except Exception:
            pass

    # Ensure we have a header frame and a placeholder for persistent header
    # controls. setup_gui() normally creates these and attaches them to the
    # `app` object, but when initialize_game_gui is called directly we need
    # to handle the case where they are missing.
    header_frame = getattr(app, 'header_frame', None)
    header_controls_placeholder = getattr(app, 'header_controls_placeholder', None)
    if header_frame is None:
        header_frame = tk.Frame(app, bg="#1a1a1a")
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 0))
        setattr(app, 'header_frame', header_frame)
    if header_controls_placeholder is None:
        header_controls_placeholder = tk.Frame(header_frame, bg="#1a1a1a")
        header_controls_placeholder.pack(side=tk.RIGHT)
        setattr(app, 'header_controls_placeholder', header_controls_placeholder)

    # API Key Input
    # Place the key_frame inside the header so it remains visible
    key_frame = tk.Frame(header_frame, bg="#1a1a1a")
    key_frame.pack(side=tk.LEFT)

    key_label = tk.Label(
        key_frame, text="Enter Key:", font=("Times New Roman", 12), fg="#ffffff", bg="#1a1a1a"
    )
    key_label.pack(side=tk.RIGHT, padx=(0, 5))

    key_entry = tk.Entry(
        key_frame,
        width=30,
        font=("Times New Roman", 12),
        highlightthickness=2,
        highlightbackground="#ff0000",
        highlightcolor="#ff0000",
        bg="#0a0a0a",
        fg="#ffffff",
        insertbackground="#ff5555"
    )
    key_entry.pack(side=tk.RIGHT)

    # API Status Label
    api_status_label = tk.Label(
        header_frame,
        text="API Status: Not Validated",
        font=("Times New Roman", 12),
        fg="#ffffff",
        bg="#1a1a1a",
    )
    api_status_label.pack(side=tk.LEFT, padx=(8, 0))

    # Ensure a logger/text_area exists; if setup_gui already created it while
    # waiting for the game, reuse it but re-pack it AFTER the key input so the
    # key entry stays visible above the log area.
    existing_logger = global_variables.get_logger()
    if existing_logger is None:
        # Place the text widget inside the log_container so the container's
        # fixed pixel size (pack_propagate(False)) prevents resizing.
        # Create a left-side frame inside the log container and place the
        # ScrolledText inside it. This mirrors the layout used in
        # setup_gui() so font-size changes do not alter widget geometry.
        parent_container = getattr(app, 'log_container', app)
        text_container = tk.Frame(parent_container, bg="#1a1a1a")
        text_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_area = scrolledtext.ScrolledText(
            text_container,
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
            font=("Times New Roman", 12)
        )
        text_area.place(x=0, y=0, relwidth=1, relheight=1)
        global_variables.set_logger(text_area)
    else:
        # reuse existing text area from earlier; leave its placement alone so
        # the pixel-sized container created in setup_gui() continues to control
        # geometry and font changes won't resize the window.
        text_area = existing_logger.text_widget

    # Function to validate the key

    def validate_saved_key():
        key_frame.pack()
        saved_key = load_existing_key(api_status_label, rsi_handle)  # Retrieve the saved key
        if saved_key:
            global_variables.log(f"Validating saved key")
            if validate_api_key(saved_key, rsi_handle):  # Validate the saved key
                api_status_label.config(text="Status: Key Validated", fg="green")
                global_variables.log("Key is Valid")
                key_frame.pack_forget()  # Hide the key entry and button if the key is valid
                # Create and show the Load Previous Logs controls now that the key is validated
                try:
                    # Place the load previous logs button into the header placeholder
                    backup_loader.create_load_prev_controls(app, text_area, BUTTON_STYLE, controls_parent=header_controls_placeholder)
                except Exception as e:
                    global_variables.log(f"Error creating backup controls: {e}")
            else:
                global_variables.log("KEY IS INVALID. Please re-enter a valid key from the Discord bot using /key-create.")
                api_status_label.config(text="Status: API Key Invalid", fg="red")
        else:
            global_variables.log("No key found. Please enter a key.")
            api_status_label.config(text="Status: No Key Found", fg="red")

    # Ensure the font control frame and buttons exist (in case
    # initialize_game_gui() is run directly and setup_gui() didn't create
    # persistent controls). Place the controls into the log_container so they
    # appear to the right of the text area and keep a fixed pixel width so
    # font changes don't influence overall geometry.
    # Ensure font controls are present in the header placeholder. If
    # setup_gui already created them, skip creation to avoid duplicates.
    if getattr(app, 'inc_btn', None) is None:
        try:
            parent = getattr(app, 'header_controls_placeholder', getattr(app, 'log_container', app))
            font_control_frame = getattr(app, 'font_control_frame', None)
            if font_control_frame is None:
                font_control_frame = tk.Frame(parent, bg="#1a1a1a")
                font_control_frame.config(width=72)
                font_control_frame.pack_propagate(False)
                font_control_frame.pack(side=tk.RIGHT, padx=(8, 0), fill=tk.Y)
                setattr(app, 'font_control_frame', font_control_frame)

            def _change_font(delta):
                try:
                    f = tkFont.Font(font=text_area['font'])
                    current_size = f.actual('size')
                    new_size = max(6, int(current_size) + delta)
                    new_font = (f.actual('family'), new_size)
                    text_area.config(font=new_font)
                except Exception as e:
                    global_variables.log(f"Error changing font size: {e}")

            def increase_font():
                _change_font(1)

            def decrease_font():
                _change_font(-1)

            inc_btn = tk.Button(font_control_frame, text="A+", command=increase_font, **BUTTON_STYLE)
            dec_btn = tk.Button(font_control_frame, text="A-", command=decrease_font, **BUTTON_STYLE)
            font_control_frame.columnconfigure(0, weight=1)
            font_control_frame.columnconfigure(1, weight=1)
            inc_btn.grid(row=0, column=0, padx=(2, 2), pady=4)
            dec_btn.grid(row=0, column=1, padx=(2, 2), pady=4)
            setattr(app, 'inc_btn', inc_btn)
            setattr(app, 'dec_btn', dec_btn)
        except Exception:
            # Non-fatal; controls are optional.
            pass

    # Automatically validate the saved key
    validate_saved_key()

    # Activate API Key
    def activate_key():
        key_frame.pack()
        entered_key = key_entry.get().strip()  # Access key_entry here
        if entered_key:
            if log_file_location:
                if player_name:
                    if validate_api_key(entered_key, rsi_handle):  # Pass both the key and player name
                        save_api_key(entered_key)  # Save the key for future use
                        global_variables.set_key(entered_key)  # Set the key in the global state
                        global_variables.log("Key activated and saved. Servitor connection established.")
                        api_status_label.config(text="Status: Validated and Saved", fg="green")
                        key_frame.pack_forget()  # Hide the key entry and button if the key is valid
                        # Create and show the Load Previous Logs controls now that the key is validated
                        try:
                            backup_loader.create_load_prev_controls(app, text_area, BUTTON_STYLE, controls_parent=header_controls_placeholder)
                        except Exception as e:
                            global_variables.log(f"Error creating backup controls: {e}")
                    else:
                        global_variables.log("Invalid key. Please enter a valid API key.")
                        api_status_label.config(text="Status: Invalid Key", fg="red")
                else:
                    global_variables.log("RSI Handle not found. Please ensure the game is running and the log file is accessible.")
                    api_status_label.config(text="Status: RSI Handle Not Found", fg="yellow")
            else:
                global_variables.log("Log file location not found.")
                api_status_label.config(text="Status: No Key Found", fg="yellow")
        else:
            global_variables.log("No key entered. Please input a valid key.")
            api_status_label.config(text="Status: No Key", fg="red")

    # The 'Load Previous Logs' button is created in setup_gui() so it is visible
    # while waiting for the game; no need to recreate it here.

    activate_button = tk.Button(
        key_frame,
        text="Activate",
        command=activate_key,
        **BUTTON_STYLE
    )
    activate_button.pack(side=tk.RIGHT, padx=(5, 0))

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