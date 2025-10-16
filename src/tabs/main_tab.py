import os
from datetime import datetime, timezone, timedelta
import tkinter as tk
from typing import Dict, Any, Optional, Callable
from PIL import Image, ImageTk
import global_variables
from tabs.details_window import open_details_window

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

    # Preload small icons used on kill cards (rifle for FPS, gladius for ship)
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
        rifle_path = os.path.join(project_root, 'rifle.png')
        gladius_path = os.path.join(project_root, 'gladius.png')
        icon_rifle = None
        icon_ship = None
        if os.path.isfile(rifle_path):
            try:
                _rifle_img = Image.open(rifle_path).resize((20, 20), Image.Resampling.LANCZOS)
                icon_rifle = ImageTk.PhotoImage(_rifle_img)
            except Exception:
                icon_rifle = None
        if os.path.isfile(gladius_path):
            try:
                _ship_img = Image.open(gladius_path).resize((20, 20), Image.Resampling.LANCZOS)
                icon_ship = ImageTk.PhotoImage(_ship_img)
            except Exception:
                icon_ship = None
        if icon_rifle is not None:
            widgets['icon_rifle'] = icon_rifle
            try:
                setattr(app, 'icon_rifle', icon_rifle)
            except Exception:
                pass
        if icon_ship is not None:
            widgets['icon_ship'] = icon_ship
            try:
                setattr(app, 'icon_ship', icon_ship)
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

    # Center container for key widgets (keeps label+entry centered horizontally)
    key_center = tk.Frame(key_section, bg="#1a1a1a")
    key_center.pack(side=tk.TOP)

    key_label = tk.Label(
        key_center, text="Enter Key:", font=("Times New Roman", 12), fg="#ffffff", bg="#1a1a1a"
    )
    key_label.pack(side=tk.LEFT, padx=(0, 8))

    key_entry = tk.Entry(
        key_center,
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

    # Activate button (kept centered alongside the key entry)
    try:
        act_style = getattr(app, 'BUTTON_STYLE', {})
    except Exception:
        act_style = {}
    activate_button = tk.Button(key_center, text="Activate", **act_style)
    activate_button.pack(side=tk.LEFT, padx=(8, 0))

    # Help/instructions shown when a key is required
    try:
        help_text = (
            "How to get a key:\n"
            "1. Open the IronPoint Discord\n"
            "2. In any channel, type /key-create\n"
            "3. Copy-paste the key into the field above"
        )
        key_help_label = tk.Label(
            key_section,
            text=help_text,
            font=("Times New Roman", 12),
            fg="#bcbcd8",
            bg="#1a1a1a",
            justify="left",
            wraplength=600,
        )
        key_help_label.pack(side=tk.TOP, pady=(6, 2))
    except Exception:
        key_help_label = None

    # API status label removed in favor of banner indicator square

    # --- Two-column layout for kills (fills remaining space under key section) ---
    # Helper to create a scrollable column with a header
    def _make_scrollable_column(master: tk.Misc, title: str) -> Dict[str, Any]:
        colors = {
            'bg': '#1a1a1a',
            'card_bg': '#0f0f0f',
            'fg': '#ffffff',
            'muted': '#bcbcd8',
            'accent': '#ff5555',
            'border': '#2a2a2a',
        }

        outer = tk.Frame(master, bg=colors['bg'])
        header = tk.Label(
            outer,
            text=title,
            font=("Times New Roman", 14, "bold"),
            fg=colors['fg'],
            bg=colors['bg']
        )
        header.pack(side=tk.TOP, anchor='w', padx=6, pady=(0, 6))

        content = tk.Frame(outer, bg=colors['bg'])
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(content, bg=colors['bg'], highlightthickness=0, bd=0)
        vbar = tk.Scrollbar(content, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)

        # The internal frame that will host cards
        inner = tk.Frame(canvas, bg=colors['bg'])
        window_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _update_scrollregion(event=None):
            try:
                canvas.configure(scrollregion=canvas.bbox('all'))
            except Exception:
                pass

        def _resize_inner(event):
            try:
                canvas.itemconfig(window_id, width=event.width)
            except Exception:
                pass

        inner.bind('<Configure>', _update_scrollregion)
        canvas.bind('<Configure>', _resize_inner)

        # Mouse wheel support (bind on canvas so it remains active over child widgets)
        def _on_mousewheel(event):
            try:
                # On Windows, event.delta is a multiple of 120 per notch
                steps = int(-1 * (event.delta / 120)) if event.delta != 0 else 0
                if steps:
                    canvas.yview_scroll(steps, 'units')
            except Exception:
                pass

        canvas.bind('<Enter>', lambda e: canvas.bind_all('<MouseWheel>', _on_mousewheel))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)

        return {
            'outer': outer,
            'header': header,
            'canvas': canvas,
            'scrollbar': vbar,
            'container': inner,
        }

    # Helper to create a themed kill card and attach to a container
    def _add_kill_card(
        container: tk.Misc,
        primary_text: str,
        secondary_text: Optional[str] = None,
        meta_text: Optional[str] = None,
        icon: Optional[ImageTk.PhotoImage] = None,
        accent_color: Optional[str] = None,
        border_color: Optional[str] = None,
        insert_top: bool = False,
    ):
        colors = {
            'bg': '#1a1a1a',
            'card_bg': '#0f0f0f',
            'fg': '#ffffff',
            'muted': '#bcbcd8',
            'accent': '#ff5555',
            'border': '#2a2a2a',
        }
        try:
            outline = border_color if (isinstance(border_color, str) and border_color.strip()) else colors['border']
        except Exception:
            outline = colors['border']
        card = tk.Frame(container, bg=colors['card_bg'], highlightthickness=1, highlightbackground=outline)

        # Left accent bar
        try:
            bar_color = accent_color if (isinstance(accent_color, str) and accent_color.strip()) else colors['accent']
        except Exception:
            bar_color = colors['accent']
        tk.Frame(card, bg=bar_color, width=4).pack(side=tk.LEFT, fill=tk.Y)

        # Optional right-side icon (kept as attribute reference to avoid GC)
        if icon is not None:
            try:
                icon_lbl = tk.Label(card, image=icon, bg=colors['card_bg'])
                icon_lbl.image = icon
                icon_lbl.pack(side=tk.RIGHT, padx=8, pady=6)
            except Exception:
                pass

        body = tk.Frame(card, bg=colors['card_bg'])
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=6)

        tk.Label(body, text=primary_text, font=("Times New Roman", 12, "bold"), fg=colors['fg'], bg=colors['card_bg']).pack(anchor='w')
        if secondary_text:
            tk.Label(body, text=secondary_text, font=("Times New Roman", 11), fg=colors['muted'], bg=colors['card_bg']).pack(anchor='w')
        if meta_text:
            tk.Label(body, text=meta_text, font=("Times New Roman", 10), fg=colors['muted'], bg=colors['card_bg']).pack(anchor='w', pady=(2, 0))

        # Mouse wheel is handled at the canvas level; no per-card bindings needed

        # Insert at top (newest first) or append to bottom
        if insert_top:
            try:
                children = list(container.winfo_children())
                if children:
                    card.pack(fill=tk.X, padx=6, pady=(0, 6), before=children[0])
                else:
                    card.pack(fill=tk.X, padx=6, pady=(0, 6))
            except Exception:
                card.pack(fill=tk.X, padx=6, pady=(0, 6))
        else:
            card.pack(fill=tk.X, padx=6, pady=(0, 6))
        return card

    # Container that will hold both columns and middle button
    columns_frame = tk.Frame(parent, bg="#1a1a1a")
    columns_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    # Use grid with three columns: left (PU), middle (Details button), right (AC)
    columns_frame.grid_rowconfigure(0, weight=1)
    columns_frame.grid_columnconfigure(0, weight=1)
    columns_frame.grid_columnconfigure(1, weight=0)
    columns_frame.grid_columnconfigure(2, weight=1)

    left_title = "PU Kills"
    right_title = "AC Kills"
    left_col = _make_scrollable_column(columns_frame, left_title)
    right_col = _make_scrollable_column(columns_frame, right_title)

    # Small gap between columns with a middle frame for the Details button
    left_col['outer'].grid(row=0, column=0, sticky='nsew', padx=(0, 4))
    # Middle container for the Details button
    middle_col = tk.Frame(columns_frame, bg="#1a1a1a")
    middle_col.grid(row=0, column=1, sticky='n', padx=4)
    right_col['outer'].grid(row=0, column=2, sticky='nsew', padx=(4, 0))

    # Helpers to show/hide the PU/AC columns and the Details button (used when key entry is visible)
    def hide_kill_columns():
        try:
            left_col['outer'].grid_remove()
        except Exception:
            pass
        try:
            right_col['outer'].grid_remove()
        except Exception:
            pass
        try:
            middle_col.grid_remove()
        except Exception:
            pass

    def show_kill_columns():
        try:
            # grid_remove remembers placement; calling grid() restores it
            left_col['outer'].grid()
        except Exception:
            pass
        try:
            right_col['outer'].grid()
        except Exception:
            pass
        try:
            middle_col.grid()
        except Exception:
            pass

    # Details window helper
    # Use external details window module

    # Single Details button centered between PU and AC columns
    try:
        style = getattr(app, 'BUTTON_STYLE', {})
    except Exception:
        style = {}
    details_btn = tk.Button(middle_col, text="Details", command=lambda: open_details_window(app), **style)
    details_btn.pack(side=tk.TOP, pady=(28, 0))

    # Header count helpers
    def _set_header_count(col: Dict[str, Any], base_title: str, count: int):
        try:
            hdr = col.get('header')
            if hdr is not None:
                hdr.config(text=f"{base_title} ({int(count)})")
        except Exception:
            pass

    # Initialize counters on the app so other modules can read/update
    try:
        if not hasattr(app, 'pu_kills_count'):
            setattr(app, 'pu_kills_count', 0)
        if not hasattr(app, 'ac_kills_count'):
            setattr(app, 'ac_kills_count', 0)
    except Exception:
        pass

    def set_pu_kills_count(n: int):
        try:
            setattr(app, 'pu_kills_count', int(n))
        except Exception:
            pass
        _set_header_count(left_col, left_title, int(n))

    def set_ac_kills_count(n: int):
        try:
            setattr(app, 'ac_kills_count', int(n))
        except Exception:
            pass
        _set_header_count(right_col, right_title, int(n))

    def inc_pu_kills_count(delta: int = 1):
        try:
            cur = int(getattr(app, 'pu_kills_count', 0)) + int(delta)
        except Exception:
            cur = 0
        set_pu_kills_count(cur)

    def inc_ac_kills_count(delta: int = 1):
        try:
            cur = int(getattr(app, 'ac_kills_count', 0)) + int(delta)
        except Exception:
            cur = 0
        set_ac_kills_count(cur)

    # Initialize headers with (0)
    try:
        _set_header_count(left_col, left_title, int(getattr(app, 'pu_kills_count', 0)))
        _set_header_count(right_col, right_title, int(getattr(app, 'ac_kills_count', 0)))
    except Exception:
        pass

    # Public helpers for controllers to add/clear cards later
    def add_pu_kill_card(title: str, subtitle: Optional[str] = None, meta: Optional[str] = None, icon: Optional[ImageTk.PhotoImage] = None, accent_color: Optional[str] = None, border_color: Optional[str] = None, insert_top: bool = False):
        card = _add_kill_card(left_col['container'], title, subtitle, meta, icon=icon, accent_color=accent_color, border_color=border_color, insert_top=insert_top)
        # Keep only the last 10 cards to limit memory usage
        try:
            children = list(left_col['container'].winfo_children())
            if len(children) > 10:
                for old in children[10:]:
                    try:
                        old.destroy()
                    except Exception:
                        pass
        except Exception:
            pass
        return card

    def add_ac_kill_card(title: str, subtitle: Optional[str] = None, meta: Optional[str] = None, icon: Optional[ImageTk.PhotoImage] = None, accent_color: Optional[str] = None, border_color: Optional[str] = None, insert_top: bool = False):
        card = _add_kill_card(right_col['container'], title, subtitle, meta, icon=icon, accent_color=accent_color, border_color=border_color, insert_top=insert_top)
        # Keep only the last 10 cards to limit memory usage
        try:
            children = list(right_col['container'].winfo_children())
            if len(children) > 10:
                for old in children[10:]:
                    try:
                        old.destroy()
                    except Exception:
                        pass
        except Exception:
            pass
        return card

    def clear_pu_kills():
        for child in list(left_col['container'].winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

    def clear_ac_kills():
        for child in list(right_col['container'].winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

    # Refresh lists from the combined API-like kills list (API + live)
    def refresh_kill_columns():
        try:
            all_items = global_variables.get_api_kills_all() or []
        except Exception:
            all_items = []

        # Deduplicate by (timestamp, victims, game_mode)
        seen = set()
        pu_items = []
        ac_items = []

        def _is_ac_mode(mode: str) -> bool:
            m = (mode or '').lower()
            return m in (
                'arena_commander', 'ac', 'electronic_access', 'ea_starfighter',
                'ea_duel', 'ea_freeflight', 'ea_vanduul_swarm'
            ) or any(x in m for x in ('arena', 'electronic access'))

        # Normalize and split
        for it in all_items:
            try:
                ts = str(it.get('timestamp') or '').strip()
                # victims is a list; use first for display, full for dedupe key
                victims_list = it.get('victims') if isinstance(it.get('victims'), list) else []
                key = (ts, tuple(victims_list), (it.get('game_mode') or '').upper())
                if key in seen:
                    continue
                seen.add(key)
                if _is_ac_mode(it.get('game_mode') or ''):
                    ac_items.append(it)
                else:
                    pu_items.append(it)
            except Exception:
                continue

        # Sort by timestamp descending
        def _parse_ts(s: str):
            try:
                if not s:
                    return None
                st = s.strip()
                if st.startswith('<') and st.endswith('>'):
                    st = st[1:-1].strip()
                if st.endswith('Z'):
                    try:
                        return datetime.strptime(st, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                    except Exception:
                        return datetime.strptime(st, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                dt = datetime.fromisoformat(st)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                return None

        def _sort_key(it):
            dt = _parse_ts(str(it.get('timestamp') or ''))
            return dt or datetime.fromtimestamp(0, tz=timezone.utc)

        pu_items_sorted = sorted(pu_items, key=_sort_key, reverse=True)
        ac_items_sorted = sorted(ac_items, key=_sort_key, reverse=True)

        # Update headers with grand totals
        try:
            set_pu_kills_count(len(pu_items_sorted))
        except Exception:
            pass
        try:
            set_ac_kills_count(len(ac_items_sorted))
        except Exception:
            pass

        # Clear existing cards
        clear_pu_kills()
        clear_ac_kills()

        # Render latest 10 for each
        now = datetime.now(timezone.utc)
        def _is_recent(ts: str) -> bool:
            dt = _parse_ts(ts)
            if not dt:
                return False
            return (now - dt) <= timedelta(hours=24)

        def _render_list(items, add_fn):
            if not callable(add_fn):
                return
            for rec in items[:10]:
                try:
                    victims = rec.get('victims') if isinstance(rec.get('victims'), list) else []
                    title = (victims[0] if victims else 'Unknown Victim')
                    ship_killed = rec.get('ship_killed')
                    is_fps = isinstance(ship_killed, str) and ship_killed.strip().upper() == 'FPS'
                    icon = getattr(app, 'icon_rifle', None) if is_fps else getattr(app, 'icon_ship', None)
                    accent = '#ff5555' if is_fps else '#3b82f6'
                    border = '#c9b037' if _is_recent(str(rec.get('timestamp') or '')) else None
                    # Append in sorted (descending) order to keep newest at top
                    add_fn(title, None, None, icon, accent, border, False)
                except Exception:
                    continue

        _render_list(pu_items_sorted, widgets.get('add_pu_kill_card'))
        _render_list(ac_items_sorted, widgets.get('add_ac_kill_card'))

    widgets.update({
        'key_section': key_section,
        'key_entry': key_entry,
        'activate_button': activate_button,
    'key_help_label': key_help_label,
        'pu_kills_frame': left_col['container'],
        'ac_kills_frame': right_col['container'],
        'pu_kills_outer': left_col['outer'],
        'ac_kills_outer': right_col['outer'],
    'details_container': middle_col,
    'details_button': details_btn,
        'add_pu_kill_card': add_pu_kill_card,
        'add_ac_kill_card': add_ac_kill_card,
        'clear_pu_kills': clear_pu_kills,
        'clear_ac_kills': clear_ac_kills,
        'refresh_kill_columns': refresh_kill_columns,
        'set_pu_kills_count': set_pu_kills_count,
        'set_ac_kills_count': set_ac_kills_count,
        'inc_pu_kills_count': inc_pu_kills_count,
        'inc_ac_kills_count': inc_ac_kills_count,
        'hide_kill_columns': hide_kill_columns,
        'show_kill_columns': show_kill_columns,
    })
    return widgets
