import tkinter as tk
from typing import Dict, Any, List, Tuple
import threading

import global_variables as gv
try:
    # When imported as 'src.tabs.piracy_tab'
    from .. import ironpoint_api  # type: ignore
except Exception:
    # When imported as 'tabs.piracy_tab'
    import ironpoint_api  # type: ignore

# Builds the Piracy tab contents with four areas:
# TL: leaderboard for most aUEC stolen
# TR: leaderboard for most pirate hits made
# BL: two leaderboards for most FPS kills (AC and PU)
# BR: functional area for buttons and actions

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

    yscroll = tk.Scrollbar(content, orient='vertical')
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
    lb.configure(yscrollcommand=yscroll.set)
    yscroll.configure(command=lb.yview)

    lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    yscroll.pack(side=tk.RIGHT, fill=tk.Y)

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
                lb.insert(tk.END, f"{i}. {text_val} - {name}")
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
                lb.insert(tk.END, f"{i}. {text_val} - {name}")
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
        'scrollbar': yscroll,
        'set_items': set_items,
        'set_items_and_ids': set_items_and_ids,
        'clear': clear,
        'highlight_user': highlight_user,
    }


def build(parent: tk.Misc) -> Dict[str, Any]:
    refs: Dict[str, Any] = {}

    # Header/label
    try:
        tk.Label(parent, text="Piracy", fg=COLORS['muted'], bg=COLORS['bg'], font=("Times New Roman", 12)).pack(anchor='nw', padx=6, pady=(6, 4))
    except Exception:
        pass

    # Main container: left = charts (2x2), right = slim Actions strip
    content_container = tk.Frame(parent, bg=COLORS['bg'], highlightthickness=1, highlightbackground=COLORS['border'])
    content_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
    refs['piracy_content_container'] = content_container

    # Configure main grid: 1 row, 2 columns (left charts, right actions)
    try:
        content_container.grid_rowconfigure(0, weight=1)
        content_container.grid_columnconfigure(0, weight=1)  # charts area grows
        content_container.grid_columnconfigure(1, weight=0, minsize=110)  # slimmer actions strip
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

    # Top-left: Most aUEC Stolen
    tl = _make_listbox_section(charts_outer, "Most aUEC Stolen")
    tl['outer'].grid(row=0, column=0, sticky='nsew', padx=(0, 3), pady=(0, 3))
    refs['au_ec_leaderboard'] = tl

    # Top-right: Most Pirate Hits Made
    tr = _make_listbox_section(charts_outer, "Most Pirate Hits Made")
    tr['outer'].grid(row=0, column=1, sticky='nsew', padx=(3, 0), pady=(0, 3))
    refs['pirate_hits_leaderboard'] = tr

    # Bottom-left: FPS Kills (AC)
    bl_ac = _make_listbox_section(charts_outer, "FPS Kills (AC)")
    bl_ac['outer'].grid(row=1, column=0, sticky='nsew', padx=(0, 3), pady=(3, 0))
    refs['fps_kills_ac'] = bl_ac

    # Bottom-right: FPS Kills (PU)
    bl_pu = _make_listbox_section(charts_outer, "FPS Kills (PU)")
    bl_pu['outer'].grid(row=1, column=1, sticky='nsew', padx=(3, 0), pady=(3, 0))
    refs['fps_kills_pu'] = bl_pu

    # Right-side Actions strip
    br_outer = tk.Frame(content_container, bg=COLORS['bg'], highlightthickness=1, highlightbackground=COLORS['border'])
    br_outer.grid(row=0, column=1, sticky='ns', padx=(3, 6), pady=6)
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
        """Fetch latest patch and leaderboard data from the IronPoint API and update UI."""
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
                # Most aUEC Stolen: from piracy_rows total_value sum per player
                # API rows already represent totals per player, so use total_value and hits_created
                stolen_items = []  # (display_name, value)
                hits_items = []    # (display_name, value)
                stolen_ids: List[str] = []
                hits_ids: List[str] = []
                for r in piracy_rows:
                    user_ident = r.get("player_id") or r.get("user_id") or ""
                    total_value = r.get("total_value", 0) or 0
                    hits_created = r.get("hits_created", 0) or 0
                    # Coerce strings to ints if necessary
                    try:
                        total_value = int(total_value)
                    except Exception:
                        total_value = 0
                    try:
                        hits_created = int(hits_created)
                    except Exception:
                        hits_created = 0
                    stolen_items.append((user_ident or "Unknown", total_value))
                    hits_items.append((user_ident or "Unknown", hits_created))
                    stolen_ids.append(str(user_ident))
                    hits_ids.append(str(user_ident))

                # Resolve display names for all unique IDs used in these lists
                try:
                    ids_for_names = [n for n, _ in stolen_items] + [n for n, _ in hits_items]
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

                # Replace IDs with display names
                stolen_items = [(name_map.get(n, n), v) for n, v in stolen_items]
                hits_items = [(name_map.get(n, n), v) for n, v in hits_items]

                # Sort desc
                stolen_items.sort(key=lambda x: x[1], reverse=True)
                hits_items.sort(key=lambda x: x[1], reverse=True)
                # Maintain same ordering for ids after sort by recomputing order
                def _sort_with_ids(items, ids):
                    pairs = list(zip(items, ids))
                    pairs.sort(key=lambda p: p[0][1], reverse=True)
                    sorted_items = [p[0] for p in pairs]
                    sorted_ids = [p[1] for p in pairs]
                    return sorted_items, sorted_ids

                stolen_items, stolen_ids = _sort_with_ids(stolen_items, stolen_ids)
                hits_items, hits_ids = _sort_with_ids(hits_items, hits_ids)

                tl['set_items_and_ids'](stolen_items[:100], stolen_ids[:100])
                tr['set_items_and_ids'](hits_items[:100], hits_ids[:100])
            except Exception:
                pass

            # FPS kills from blackbox rows
            try:
                ac_items = []
                pu_items = []
                ac_ids: List[str] = []
                pu_ids: List[str] = []
                for r in blackbox_rows:
                    user_ident = r.get("user_id") or r.get("player_id") or ""
                    ac = r.get("fps_kills_ac", 0) or 0
                    pu = r.get("fps_kills_pu", 0) or 0
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
                # Resolve names for FPS lists
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

                ac_items = [(name_map.get(n, n), v) for n, v in ac_items]
                pu_items = [(name_map.get(n, n), v) for n, v in pu_items]

                # Keep ids aligned with sorted items
                def _sort_with_ids(items, ids):
                    pairs = list(zip(items, ids))
                    pairs.sort(key=lambda p: p[0][1], reverse=True)
                    sorted_items = [p[0] for p in pairs]
                    sorted_ids = [p[1] for p in pairs]
                    return sorted_items, sorted_ids

                ac_items, ac_ids = _sort_with_ids(ac_items, ac_ids)
                pu_items, pu_ids = _sort_with_ids(pu_items, pu_ids)

                bl_ac['set_items_and_ids'](ac_items[:100], ac_ids[:100])
                bl_pu['set_items_and_ids'](pu_items[:100], pu_ids[:100])
            except Exception:
                pass

            # Highlight current user if present
            try:
                current_uid = gv.get_user_id()
                if current_uid:
                    tl['highlight_user'](current_uid)
                    tr['highlight_user'](current_uid)
                    bl_ac['highlight_user'](current_uid)
                    bl_pu['highlight_user'](current_uid)
            except Exception:
                pass

            try:
                gv.log(f"Piracy data loaded for patch {patch_version}: piracy rows={len(piracy_rows)}, blackbox rows={len(blackbox_rows)}")
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
                    # Fallback to known patch if stored
                    latest_patch = gv.get_patch_version() or ""

                # Fetch data for that patch
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
                    gv.log(f"Piracy tab refresh failed: {e}")
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _placeholder_clear():
        try:
            tl['clear']()
            tr['clear']()
            bl_ac['clear']()
            bl_pu['clear']()
        except Exception:
            pass

    # Public setters on the refs dict
    def set_uec_stolen(items: List[Tuple[str, Any]]):
        tl['set_items'](items)

    def set_pirate_hits(items: List[Tuple[str, Any]]):
        tr['set_items'](items)

    def set_fps_kills_ac(items: List[Tuple[str, Any]]):
        bl_ac['set_items'](items)

    def set_fps_kills_pu(items: List[Tuple[str, Any]]):
        bl_pu['set_items'](items)

    refs.update({
        'set_uec_stolen': set_uec_stolen,
        'set_pirate_hits': set_pirate_hits,
        'set_fps_kills_ac': set_fps_kills_ac,
        'set_fps_kills_pu': set_fps_kills_pu,
        'clear_all_piracy_lists': _placeholder_clear,
    })

    # Action buttons (wire to placeholders; callers can reconfigure later)
    refresh_btn = tk.Button(btns, text="Refresh", command=_refresh_from_api, **btn_style)
    refresh_btn.pack(side=tk.TOP, fill=tk.X, padx=0, pady=(0, 6))
    clear_btn = tk.Button(btns, text="Clear", command=_placeholder_clear, **btn_style)
    clear_btn.pack(side=tk.TOP, fill=tk.X, padx=0, pady=(0, 6))
    settings_btn = tk.Button(btns, text="Settings…", command=lambda: None, **btn_style)
    settings_btn.pack(side=tk.TOP, fill=tk.X, padx=0, pady=(0, 6))

    refs.update({
        'refresh_button': refresh_btn,
        'clear_button': clear_btn,
        'settings_button': settings_btn,
    })

    # Seed with example data so the UI looks alive on first open
    try:
        _refresh_from_api()
    except Exception:
        pass

    return refs
