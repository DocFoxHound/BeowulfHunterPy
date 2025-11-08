import tkinter as tk
from typing import Dict, Any, List, Tuple
import threading
import graphs

import global_variables as gv
try:
    # When imported as 'src.tabs.dogfighting_tab'
    from .. import ironpoint_api  # type: ignore
except Exception:
    # When imported as 'tabs.dogfighting_tab'
    import ironpoint_api  # type: ignore
# Removed keys import (no longer used after removing sound pickers)

# Builds the Dogfighting tab contents mirroring the Piracy tab layout.

COLORS = {
    'bg': '#1a1a1a',
    'fg': '#ffffff',
    'muted': '#bcbcd8',
    'border': '#2a2a2a',
    'card_bg': '#0f0f0f',
    'accent': '#ff5555',
    'gold': '#DAA520',
}


def _make_listbox_section(master: tk.Misc, title: str) -> Dict[str, Any]:
    """Create a titled section containing a Listbox + vertical scrollbar.

    Returns dict with keys: outer, header, listbox, scrollbar, set_items, clear
    """
    outer = tk.Frame(master, bg=COLORS['bg'], highlightthickness=1, highlightbackground=COLORS['border'])
    header = tk.Label(outer, text=title, fg=COLORS['fg'], bg=COLORS['bg'], font=("Times New Roman", 12, "bold"))
    header.pack(side=tk.TOP, anchor='w', padx=6, pady=(6, 4))

    content = tk.Frame(outer, bg=COLORS['bg'])
    content.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    lb = tk.Listbox(
        content,
        bg=COLORS['card_bg'],
        fg=COLORS['fg'],
        selectbackground='#333333',
        selectforeground=COLORS['fg'],
        highlightthickness=1,
        highlightbackground=COLORS['border'],
        activestyle='none',
        font=("Times New Roman", 12)
    )

    lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Keep row IDs parallel to rendered items so we can highlight a specific user
    lb._row_ids = []  # type: ignore[attr-defined]

    def _reset_row_styles():
        try:
            size = lb.size()
            for i in range(size):
                try:
                    lb.itemconfig(i, fg=COLORS['fg'], bg=COLORS['card_bg'])
                except Exception:
                    pass
        except Exception:
            pass

    def set_items(items: List[Tuple[str, Any]]):
        try:
            lb.delete(0, tk.END)
            lb._row_ids = []  # type: ignore[attr-defined]
            # items expected as list of (name, value)
            for i, (name, value) in enumerate(items, start=1):
                try:
                    if isinstance(value, (int, float)):
                        text_val = f"{value:,.0f}" if isinstance(value, int) else f"{value:,.2f}"
                    else:
                        text_val = str(value)
                except Exception:
                    text_val = str(value)
                # Show value before the name so the important number is visible even if truncated
                lb.insert(tk.END, f"{text_val} - {name}")
            _reset_row_styles()
        except Exception:
            pass

    def set_items_and_ids(items: List[Tuple[str, Any]], row_ids: List[str]):
        try:
            lb.delete(0, tk.END)
            lb._row_ids = list(row_ids) if row_ids is not None else []  # type: ignore[attr-defined]
            for i, (name, value) in enumerate(items, start=1):
                try:
                    if isinstance(value, (int, float)):
                        text_val = f"{value:,.0f}" if isinstance(value, int) else f"{value:,.2f}"
                    else:
                        text_val = str(value)
                except Exception:
                    text_val = str(value)
                # Show value before the name so the important number is visible even if truncated
                lb.insert(tk.END, f"{text_val} - {name}")
            _reset_row_styles()
        except Exception:
            pass

    def clear():
        try:
            lb.delete(0, tk.END)
            try:
                lb._row_ids = []  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            pass

    def highlight_user(user_id: str):
        """Highlight any rows belonging to the provided user_id in gold."""
        try:
            _reset_row_styles()
            if not user_id:
                return
            ids = getattr(lb, '_row_ids', [])
            for idx, rid in enumerate(ids):
                try:
                    if str(rid) == str(user_id):
                        lb.itemconfig(idx, fg='#000000', bg=COLORS['gold'])
                except Exception:
                    pass
        except Exception:
            pass

    return {
        'outer': outer,
        'header': header,
        'listbox': lb,
        'scrollbar': None,  # scrollbar removed to save space
        'set_items': set_items,
        'set_items_and_ids': set_items_and_ids,
        'clear': clear,
        'highlight_user': highlight_user,
    }


def build(parent: tk.Misc) -> Dict[str, Any]:
    refs: Dict[str, Any] = {}

    # Header/label
    try:
        tk.Label(parent, text="Dogfighting", fg=COLORS['muted'], bg=COLORS['bg'], font=("Times New Roman", 12)).pack(anchor='nw', padx=6, pady=(6, 4))
    except Exception:
        pass

    # Main container: left = charts (2x2), right = slim Actions strip
    content_container = tk.Frame(parent, bg=COLORS['bg'], highlightthickness=1, highlightbackground=COLORS['border'])
    content_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
    refs['dogfighting_content_container'] = content_container

    # Configure main grid: 1 row, 2 columns (left charts, right actions)
    try:
        content_container.grid_rowconfigure(0, weight=1)
        # Allocate ~85/15 proportion between charts and actions. Keep a small min width for actions.
        content_container.grid_columnconfigure(0, weight=85)  # charts area grows
        content_container.grid_columnconfigure(1, weight=15, minsize=130)  # actions strip ~15%
    except Exception:
        pass

    # Charts outer frame (2x2 grid inside)
    charts_outer = tk.Frame(content_container, bg=COLORS['bg'])
    charts_outer.grid(row=0, column=0, sticky='nsew', padx=(6, 3), pady=6)
    try:
        charts_outer.grid_rowconfigure(0, weight=1)
        charts_outer.grid_rowconfigure(1, weight=1)
        charts_outer.grid_columnconfigure(0, weight=1)
        charts_outer.grid_columnconfigure(1, weight=1)
    except Exception:
        pass

    # Top-left: Top Ranked Arena Commander (by rating)
    tl = _make_listbox_section(charts_outer, "Squadron Battle - Top Rated")
    tl['outer'].grid(row=0, column=0, sticky='nsew', padx=(0, 3), pady=(0, 3))
    # Keep old key for back-compat and provide a clearer alias
    refs['au_ec_leaderboard'] = tl
    refs['top_ranked_ac_leaderboard'] = tl

    # Top-right: Most PU damages
    tr = _make_listbox_section(charts_outer, "Most PU Damages")
    tr['outer'].grid(row=0, column=1, sticky='nsew', padx=(3, 0), pady=(0, 3))
    # Keep old key for back-compat and provide a clearer alias
    refs['pirate_hits_leaderboard'] = tr
    refs['pu_damages_leaderboard'] = tr

    # Bottom-left: Ship Kills (AC)
    bl_ship_ac = _make_listbox_section(charts_outer, "Ship Kills (AC)")
    bl_ship_ac['outer'].grid(row=1, column=0, sticky='nsew', padx=(0, 3), pady=(3, 0))
    # Back-compat aliases plus new keys
    refs['ship_kills_ac'] = bl_ship_ac
    refs['fps_kills_ac'] = bl_ship_ac

    # Bottom-right: Ship Kills (PU)
    bl_ship_pu = _make_listbox_section(charts_outer, "Ship Kills (PU)")
    bl_ship_pu['outer'].grid(row=1, column=1, sticky='nsew', padx=(3, 0), pady=(3, 0))
    # Back-compat aliases plus new keys
    refs['ship_kills_pu'] = bl_ship_pu
    refs['fps_kills_pu'] = bl_ship_pu

    # Right-side Actions strip
    br_outer = tk.Frame(content_container, bg=COLORS['bg'], highlightthickness=1, highlightbackground=COLORS['border'])
    # Fill the right-side column horizontally and vertically
    br_outer.grid(row=0, column=1, sticky='nsew', padx=(3, 6), pady=6)
    refs['actions_area'] = br_outer

    actions_header = tk.Label(br_outer, text="Actions", fg=COLORS['fg'], bg=COLORS['bg'], font=("Times New Roman", 12, "bold"))
    actions_header.pack(side=tk.TOP, anchor='w', padx=6, pady=(6, 4))

    # Buttons container
    btns = tk.Frame(br_outer, bg=COLORS['bg'])
    btns.pack(side=tk.TOP, anchor='nw', fill=tk.X, padx=6, pady=(0, 6))

    # Button style (fallback if not provided by app)
    btn_style = {
        "bg": "#0f0f0f",
        "fg": "#ff5555",
        "activebackground": "#330000",
        "activeforeground": "#ffffff",
        "relief": "ridge",
        "bd": 2,
        "font": ("Times New Roman", 12),
    }

    def _refresh_from_api():
        """Fetch latest patch and leaderboard data from the IronPoint API and update UI.

        Currently mirrors the Piracy tab behavior.
        """
        app = gv.get_app()

        def _update_ui(patch_version: str,
                        piracy_rows: List[dict],
                        blackbox_rows: List[dict]):
            # Save patch version globally
            try:
                gv.set_patch_version(patch_version)
            except Exception:
                pass

            # Build leaderboards
            try:
                # Top-right: Most PU $ in Damages (from blackbox summary value_pu)
                damages_items = []    # (display_name, value_pu)
                damages_ids: List[str] = []
                for r in blackbox_rows:
                    user_ident = r.get("user_id") or r.get("player_id") or ""
                    value_pu = r.get("value_pu", 0) or 0
                    try:
                        value_pu = int(value_pu)
                    except Exception:
                        try:
                            value_pu = float(value_pu)
                        except Exception:
                            value_pu = 0
                    damages_items.append((user_ident or "Unknown", value_pu))
                    damages_ids.append(str(user_ident))

                # Top-left: Top Ranked Arena Commander (by rating from blackbox summary)
                rating_items = []  # (display_name, rating)
                rating_ids: List[str] = []
                for r in blackbox_rows:
                    user_ident = r.get("user_id") or r.get("player_id") or ""
                    rating = r.get("rating", 0) or 0
                    try:
                        rating = float(rating)
                    except Exception:
                        rating = 0.0
                    rating_items.append((user_ident or "Unknown", rating))
                    rating_ids.append(str(user_ident))

                # Resolve display names for all unique IDs used in these lists
                try:
                    ids_for_names = [n for n, _ in rating_items] + [n for n, _ in damages_items]
                    name_map = ironpoint_api.resolve_user_display_names(ids_for_names)
                except Exception:
                    name_map = {}

                # Ensure current user's nickname is shown even if not in filtered cache
                try:
                    cur_uid = gv.get_user_id()
                    if cur_uid:
                        friendly = ironpoint_api.get_user_display_name_fallback(cur_uid)
                        if isinstance(friendly, str) and friendly and friendly != cur_uid:
                            name_map[str(cur_uid)] = friendly
                except Exception:
                    pass

                # Filter out entries without a proper nickname mapping
                def _filter_and_map(items, ids, mapping):
                    new_items = []
                    new_ids = []
                    try:
                        for (raw_name, val), rid in zip(items, ids):
                            disp = mapping.get(rid)
                            if isinstance(disp, str) and disp.strip() and disp != rid:
                                new_items.append((disp, val))
                                new_ids.append(rid)
                    except Exception:
                        pass
                    return new_items, new_ids

                rating_items, rating_ids = _filter_and_map(rating_items, rating_ids, name_map)
                damages_items, damages_ids = _filter_and_map(damages_items, damages_ids, name_map)

                # Sort desc and keep ids aligned
                def _sort_with_ids(items, ids):
                    pairs = list(zip(items, ids))
                    pairs.sort(key=lambda p: p[0][1], reverse=True)
                    sorted_items = [p[0] for p in pairs]
                    sorted_ids = [p[1] for p in pairs]
                    return sorted_items, sorted_ids

                rating_items, rating_ids = _sort_with_ids(rating_items, rating_ids)
                damages_items, damages_ids = _sort_with_ids(damages_items, damages_ids)

                # Format ratings with no decimal places (rounded) for display only
                rating_items_display: List[Tuple[str, Any]] = []
                try:
                    for name, val in rating_items[:100]:
                        try:
                            # Round to nearest whole number and add commas
                            rounded = int(round(float(val)))
                            text_val = f"{rounded:,}"
                        except Exception:
                            text_val = str(val)
                        rating_items_display.append((name, text_val))
                except Exception:
                    rating_items_display = [(name, str(val)) for name, val in rating_items[:100]]

                # Format damages with a leading $ for display only
                damages_items_display: List[Tuple[str, Any]] = []
                try:
                    for name, val in damages_items[:100]:
                        try:
                            if isinstance(val, int):
                                text_val = f"${val:,}"
                            else:
                                # floats or other numerics
                                text_val = f"${float(val):,.2f}"
                        except Exception:
                            text_val = f"${val}"
                        damages_items_display.append((name, text_val))
                except Exception:
                    damages_items_display = [(name, f"${val}") for name, val in damages_items[:100]]

                tl['set_items_and_ids'](rating_items_display, rating_ids[:100])
                tr['set_items_and_ids'](damages_items_display, damages_ids[:100])
            except Exception:
                pass

            # Ship kills from blackbox rows (fallback to FPS kills if ship_* fields not present)
            try:
                ac_items = []
                pu_items = []
                ac_ids: List[str] = []
                pu_ids: List[str] = []
                for r in blackbox_rows:
                    user_ident = r.get("user_id") or r.get("player_id") or ""
                    # Prefer ship_kills_* fields; gracefully fall back to fps_kills_*
                    ac = r.get("ship_kills_ac", r.get("fps_kills_ac", 0)) or 0
                    pu = r.get("ship_kills_pu", r.get("fps_kills_pu", 0)) or 0
                    try:
                        ac = int(ac)
                    except Exception:
                        ac = 0
                    try:
                        pu = int(pu)
                    except Exception:
                        pu = 0
                    ac_items.append((user_ident or "Unknown", ac))
                    pu_items.append((user_ident or "Unknown", pu))
                    ac_ids.append(str(user_ident))
                    pu_ids.append(str(user_ident))
                # Resolve names for ship kill lists
                try:
                    ids_for_names = [n for n, _ in ac_items] + [n for n, _ in pu_items]
                    name_map = ironpoint_api.resolve_user_display_names(ids_for_names)
                except Exception:
                    name_map = {}

                # Ensure current user's nickname is shown even if not in filtered cache
                try:
                    cur_uid = gv.get_user_id()
                    if cur_uid:
                        friendly = ironpoint_api.get_user_display_name_fallback(cur_uid)
                        if isinstance(friendly, str) and friendly and friendly != cur_uid:
                            name_map[str(cur_uid)] = friendly
                except Exception:
                    pass

                # Filter out entries without a proper nickname mapping
                def _filter_and_map(items, ids, mapping):
                    new_items = []
                    new_ids = []
                    try:
                        for (raw_name, val), rid in zip(items, ids):
                            disp = mapping.get(rid)
                            if isinstance(disp, str) and disp.strip() and disp != rid:
                                new_items.append((disp, val))
                                new_ids.append(rid)
                    except Exception:
                        pass
                    return new_items, new_ids

                ac_items, ac_ids = _filter_and_map(ac_items, ac_ids, name_map)
                pu_items, pu_ids = _filter_and_map(pu_items, pu_ids, name_map)

                def _sort_with_ids(items, ids):
                    pairs = list(zip(items, ids))
                    pairs.sort(key=lambda p: p[0][1], reverse=True)
                    sorted_items = [p[0] for p in pairs]
                    sorted_ids = [p[1] for p in pairs]
                    return sorted_items, sorted_ids

                ac_items, ac_ids = _sort_with_ids(ac_items, ac_ids)
                pu_items, pu_ids = _sort_with_ids(pu_items, pu_ids)

                bl_ship_ac['set_items_and_ids'](ac_items[:100], ac_ids[:100])
                bl_ship_pu['set_items_and_ids'](pu_items[:100], pu_ids[:100])
            except Exception:
                pass

            # Highlight current user if present
            try:
                current_uid = gv.get_user_id()
                if current_uid:
                    tl['highlight_user'](current_uid)
                    tr['highlight_user'](current_uid)
                    bl_ship_ac['highlight_user'](current_uid)
                    bl_ship_pu['highlight_user'](current_uid)
            except Exception:
                pass

            try:
                gv.log(f"Dogfighting data loaded for patch {patch_version}: piracy rows={len(piracy_rows)}, blackbox rows={len(blackbox_rows)}")
            except Exception:
                pass

        def _worker():
            try:
                # Determine latest patch
                try:
                    latest_patch = ironpoint_api.get_latest_patch_version()
                except Exception:
                    latest_patch = gv.get_patch_version()
                if not latest_patch:
                    latest_patch = gv.get_patch_version() or ""

                # Fetch data for that patch (same endpoints as Piracy for now)
                piracy = ironpoint_api.get_piracy_summary(latest_patch) if latest_patch else []
                blackbox = ironpoint_api.get_blackbox_summary(latest_patch) if latest_patch else []

                # Schedule UI update on main thread
                try:
                    if app is not None:
                        app.after(0, _update_ui, latest_patch, piracy, blackbox)
                except Exception:
                    _update_ui(latest_patch, piracy, blackbox)
            except Exception as e:
                try:
                    gv.log(f"Dogfighting tab refresh failed: {e}")
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _placeholder_clear():
        try:
            tl['clear']()
            tr['clear']()
            bl_ship_ac['clear']()
            bl_ship_pu['clear']()
        except Exception:
            pass

    # Public setters on the refs dict
    def set_uec_stolen(items: List[Tuple[str, Any]]):
        tl['set_items'](items)

    def set_pirate_hits(items: List[Tuple[str, Any]]):
        tr['set_items'](items)

    # New ship kill setters
    def set_ship_kills_ac(items: List[Tuple[str, Any]]):
        bl_ship_ac['set_items'](items)

    def set_ship_kills_pu(items: List[Tuple[str, Any]]):
        bl_ship_pu['set_items'](items)

    # Back-compat FPS kill setter names route to the same sections
    def set_fps_kills_ac(items: List[Tuple[str, Any]]):
        bl_ship_ac['set_items'](items)

    def set_fps_kills_pu(items: List[Tuple[str, Any]]):
        bl_ship_pu['set_items'](items)

    refs.update({
        'set_uec_stolen': set_uec_stolen,
        'set_pirate_hits': set_pirate_hits,
        'set_ship_kills_ac': set_ship_kills_ac,
        'set_ship_kills_pu': set_ship_kills_pu,
        'set_fps_kills_ac': set_fps_kills_ac,  # alias
        'set_fps_kills_pu': set_fps_kills_pu,  # alias
        'clear_all_dogfighting_lists': _placeholder_clear,
    })

    # Action buttons (wire to placeholders; callers can reconfigure later)
    refresh_btn = tk.Button(btns, text="Refresh", command=_refresh_from_api, **btn_style)
    refresh_btn.pack(side=tk.TOP, fill=tk.X, padx=0, pady=(0, 6))
    clear_btn = tk.Button(btns, text="Clear", command=_placeholder_clear, **btn_style)
    clear_btn.pack(side=tk.TOP, fill=tk.X, padx=0, pady=(0, 6))
    # Graphs popup
    graphs_window_ref = {'win': None, 'widget': None}

    def _open_graphs_window():
        try:
            # Reuse if already open
            win = graphs_window_ref.get('win')
            if win is not None and win.winfo_exists():
                try:
                    win.deiconify()
                    win.lift()
                    win.focus_force()
                except Exception:
                    pass
                # Ensure refresh on reuse
                gw = graphs_window_ref.get('widget')
                try:
                    if gw:
                        gw.refresh(force=True)
                except Exception:
                    pass
                return

            # Create new toplevel
            win = tk.Toplevel(parent)
            win.title("BeowulfHunter – Graphs")
            try:
                win.configure(bg=COLORS['bg'])
            except Exception:
                pass
            # Nice default size; resizable
            try:
                win.geometry("700x520")
            except Exception:
                pass
            win.resizable(True, True)

            # Container for the graph widget
            container = tk.Frame(win, bg=COLORS['bg'])
            container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            try:
                gw = graphs.GraphWidget(container)
                graphs_window_ref['widget'] = gw
            except Exception:
                tk.Label(container, text="Graph unavailable", fg=COLORS['muted'], bg=COLORS['bg']).pack(padx=6, pady=6, anchor='nw')
                graphs_window_ref['widget'] = None

            graphs_window_ref['win'] = win

            def _on_close():
                try:
                    graphs_window_ref['win'] = None
                    graphs_window_ref['widget'] = None
                except Exception:
                    pass
                try:
                    win.destroy()
                except Exception:
                    pass

            try:
                win.protocol("WM_DELETE_WINDOW", _on_close)
            except Exception:
                pass
        except Exception as e:
            try:
                gv.log(f"Failed to open graphs window: {e}")
            except Exception:
                pass

    graphs_btn = tk.Button(btns, text="Graphs", command=_open_graphs_window, **btn_style)
    graphs_btn.pack(side=tk.TOP, fill=tk.X, padx=0, pady=(0, 6))

    # Removed: Custom sound pickers and overlay controls per request

    refs.update({
        'refresh_button': refresh_btn,
        'clear_button': clear_btn,
        'graphs_button': graphs_btn,
        'open_graphs_window': _open_graphs_window,
        'graphs_window_ref': graphs_window_ref,
    })

    # Seed with example data so the UI looks alive on first open
    try:
        _refresh_from_api()
    except Exception:
        pass

    return refs
