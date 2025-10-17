import tkinter as tk
from tkinter import scrolledtext
from typing import Dict, Any
import global_variables
import backup_loader

# Shared button style (kept in sync with setup_gui if imported there)
BUTTON_STYLE = {
    "bg": "#0f0f0f",
    "fg": "#ff5555",
    "activebackground": "#330000",
    "activeforeground": "#ffffff",
    "relief": "ridge",
    "bd": 2,
    "font": ("Times New Roman", 12)
}


def build(parent: tk.Misc, app) -> Dict[str, Any]:
    refs: Dict[str, Any] = {}

    # Controls row above the log text area
    log_controls_container = tk.Frame(parent, bg="#1a1a1a", highlightthickness=1, highlightbackground="#2a2a2a")
    log_controls_container.pack(side=tk.TOP, fill=tk.X, padx=0, pady=(0, 4))
    setattr(app, 'log_controls_container', log_controls_container)
    # Mark container so loaders can tailor layout (stack/inlined as needed for log tab)
    try:
        setattr(log_controls_container, '_is_log_controls_container', True)
    except Exception:
        pass

    # Log text area
    log_text_container = tk.Frame(parent, bg="#1a1a1a")
    log_text_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    text_area = scrolledtext.ScrolledText(
        log_text_container,
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
    text_area.pack(fill=tk.BOTH, expand=True)

    # Register as logger
    global_variables.set_logger(text_area)

    # Create the "Load Previous Logs" controls inside the Log tab controls container
    try:
        backup_loader.create_load_prev_controls(app, text_area, getattr(app, 'BUTTON_STYLE', BUTTON_STYLE), controls_parent=log_controls_container)
    except Exception:
        pass

    refs.update({
        'log_controls_container': log_controls_container,
        'log_text_area': text_area,
    })
    return refs
