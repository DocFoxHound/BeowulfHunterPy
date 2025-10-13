import tkinter as tk
from typing import Dict, Any, Optional, Callable
from PIL import Image, ImageTk

# This module is responsible for building content inside the Main tab.
# It returns references required later (e.g., key section widgets) so
# the rest of the app can wire up callbacks.


def build(parent: tk.Misc, app, banner_path: Optional[str] = None, update_message: Optional[str] = None, on_update_click: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Build the Main tab UI.

    Returns a dict of widget references used elsewhere in the app:
    - key_section: frame that holds the key entry and activate button
    - key_entry: entry widget for the API key
    """
    widgets: Dict[str, Any] = {}
    # Parent is a ttk.Frame (styled via 'Dark.TFrame'); no direct bg config here
    # Banner image at top of Main tab (optional)
    if banner_path:
        try:
            original_image = Image.open(banner_path)
            resized_image = original_image.resize((480, 150), Image.Resampling.LANCZOS)
            banner_image = ImageTk.PhotoImage(resized_image)
            banner_canvas = tk.Canvas(parent, width=480, height=150, bg="#1a1a1a", highlightthickness=0, bd=0)
            banner_canvas.create_image(0, 0, anchor='nw', image=banner_image)
            banner_canvas.image = banner_image
            banner_canvas.pack(pady=(0, 4))
            widgets['banner_canvas'] = banner_canvas
            # Expose on app for controllers that expect it
            try:
                setattr(app, 'banner_canvas', banner_canvas)
            except Exception:
                pass
        except Exception:
            pass

    # Update label (optional)
    if update_message:
        try:
            update_label = tk.Label(
                parent,
                text=update_message,
                font=("Times New Roman", 12),
                fg="#ff5555",
                bg="#1a1a1a",
                wraplength=700,
                justify="center",
                cursor="hand2",
            )
            update_label.pack(pady=(4, 8))
            if on_update_click is not None:
                update_label.bind("<Button-1>", lambda event: on_update_click(event, update_message))
            widgets['update_label'] = update_label
        except Exception:
            pass

    key_section = tk.Frame(parent, bg="#1a1a1a")
    key_section.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)

    key_label = tk.Label(
        key_section, text="Enter Key:", font=("Times New Roman", 12), fg="#ffffff", bg="#1a1a1a"
    )
    key_label.pack(side=tk.LEFT, padx=(0, 8))

    key_entry = tk.Entry(
        key_section,
        width=30,
        font=("Times New Roman", 12),
        highlightthickness=2,
        highlightbackground="#ff0000",
        highlightcolor="#ff0000",
        bg="#0a0a0a",
        fg="#ffffff",
        insertbackground="#ff5555"
    )
    key_entry.pack(side=tk.LEFT)

    # API status label removed in favor of banner indicator square

    # Optional placeholder label to keep parity with prior UI
    try:
        tk.Label(parent, text="Main page", fg="#bcbcd8", bg="#1a1a1a", font=("Times New Roman", 12)).pack(anchor='nw', padx=6, pady=6)
    except Exception:
        pass

    widgets.update({
        'key_section': key_section,
        'key_entry': key_entry,
    })
    return widgets
