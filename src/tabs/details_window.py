import tkinter as tk
from datetime import datetime, timezone, timedelta
from collections import Counter
import global_variables


def open_details_window(app):
    """Open the Kill Details window showing analytics and full lists (PU/AC)."""
    win = tk.Toplevel(app)
    try:
        win.title("Kill Details")
        win.configure(bg="#1a1a1a")
        win.geometry("640x420")
    except Exception:
        pass

    # header = tk.Label(
    #     win,
    #     font=("Times New Roman", 14, "bold"),
    #     fg="#ffffff",
    #     bg="#1a1a1a",
    # )
    # header.pack(side=tk.TOP, anchor='w', padx=8, pady=(8, 4))

    # Fetch combined kills
    try:
        all_items = global_variables.get_api_kills_all() or []
    except Exception:
        all_items = []

    # Analytics: Top victims, top ships killed (excluding FPS), and favorite ships used
    victim_counter = Counter()
    ship_counter = Counter()
    ship_used_counter = Counter()
    for it in all_items:
        try:
            vs = it.get('victims') if isinstance(it.get('victims'), list) else []
            for v in vs:
                if v:
                    victim_counter[v] += 1
            sk = it.get('ship_killed')
            if isinstance(sk, str) and sk.strip() and sk.strip().upper() != 'FPS':
                ship_counter[sk.strip()] += 1
            su = it.get('ship_used')
            if isinstance(su, str):
                su_s = su.strip()
                if su_s and su_s.lower() != 'null':
                    ship_used_counter[su_s] += 1
        except Exception:
            continue

    top_victims = victim_counter.most_common(3)
    top_ships = ship_counter.most_common(3)
    top_fav_ships = ship_used_counter.most_common(3)

    # Top stats row
    stats_row = tk.Frame(win, bg="#1a1a1a")
    stats_row.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 4))

    def _make_stat_box(parent, title, items):
        box = tk.Frame(parent, bg="#0f0f0f", highlightthickness=1, highlightbackground="#2a2a2a")
        tk.Label(box, text=title, font=("Times New Roman", 12, "bold"), fg="#ffffff", bg="#0f0f0f").pack(anchor='w', padx=8, pady=(6, 2))
        if not items:
            tk.Label(box, text="No data", font=("Times New Roman", 11), fg="#bcbcd8", bg="#0f0f0f").pack(anchor='w', padx=8, pady=(0, 8))
        else:
            for name, count in items:
                tk.Label(box, text=f"{name} — {count}", font=("Times New Roman", 11), fg="#bcbcd8", bg="#0f0f0f").pack(anchor='w', padx=8)
            tk.Label(box, text="", bg="#0f0f0f").pack(pady=(0, 6))
        return box

    left_box = _make_stat_box(stats_row, "Top Victims", top_victims)
    # mid_box = _make_stat_box(stats_row, "Favorite Ships", top_fav_ships)
    right_box = _make_stat_box(stats_row, "Top Ships Killed", top_ships)
    left_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4), anchor='n')
    # mid_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4), anchor='n')
    right_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0), anchor='n')

    # Below: single scrollable column with all kills (newest first)
    lists_row = tk.Frame(win, bg="#1a1a1a")
    lists_row.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _make_scrollable_column(master, title):
        colors = {
            'bg': '#1a1a1a', 'card_bg': '#0f0f0f', 'fg': '#ffffff',
            'muted': '#bcbcd8', 'accent': '#ff5555', 'border': '#2a2a2a'
        }
        outer = tk.Frame(master, bg=colors['bg'])
        header = tk.Label(outer, text=title, font=("Times New Roman", 13, "bold"), fg=colors['fg'], bg=colors['bg'])
        header.pack(side=tk.TOP, anchor='w', pady=(0, 4))
        content = tk.Frame(outer, bg=colors['bg'])
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(content, bg=colors['bg'], highlightthickness=0, bd=0)
        vbar = tk.Scrollbar(content, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
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

        # Mouse wheel support — bind on canvas so it works over children
        def _on_mousewheel(event):
            try:
                steps = int(-1 * (event.delta / 120)) if event.delta != 0 else 0
                if steps:
                    canvas.yview_scroll(steps, 'units')
            except Exception:
                pass

        canvas.bind('<Enter>', lambda e: canvas.bind_all('<MouseWheel>', _on_mousewheel))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        return {'outer': outer, 'container': inner}

    all_col = _make_scrollable_column(lists_row, "All Kills — Newest First")
    all_col['outer'].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

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

    now = datetime.now(timezone.utc)
    def _is_recent(ts: str) -> bool:
        dt = _parse_ts(ts)
        return (dt is not None) and ((now - dt) <= timedelta(hours=24))

    def _add_card(container, primary_text, secondary_text=None, meta_text=None, icon=None, accent_color=None, border_color=None):
        colors = {'bg': '#1a1a1a', 'card_bg': '#0f0f0f', 'fg': '#ffffff', 'muted': '#bcbcd8', 'accent': '#ff5555', 'border': '#2a2a2a'}
        outline = border_color if (isinstance(border_color, str) and border_color.strip()) else colors['border']
        card = tk.Frame(container, bg=colors['card_bg'], highlightthickness=1, highlightbackground=outline)
        bar = tk.Frame(card, bg=(accent_color or colors['accent']), width=4)
        bar.pack(side=tk.LEFT, fill=tk.Y)
        if icon is not None:
            try:
                lbl = tk.Label(card, image=icon, bg=colors['card_bg'])
                lbl.image = icon
                lbl.pack(side=tk.RIGHT, padx=8, pady=6)
            except Exception:
                pass
        body = tk.Frame(card, bg=colors['card_bg'])
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=6)
        tk.Label(body, text=primary_text, font=("Times New Roman", 12, "bold"), fg=colors['fg'], bg=colors['card_bg']).pack(anchor='w')
        if secondary_text:
            tk.Label(body, text=secondary_text, font=("Times New Roman", 11), fg=colors['muted'], bg=colors['card_bg']).pack(anchor='w')
        if meta_text:
            tk.Label(body, text=meta_text, font=("Times New Roman", 10), fg=colors['muted'], bg=colors['card_bg']).pack(anchor='w', pady=(2, 0))
        card.pack(fill=tk.X, padx=6, pady=(0, 6))

    # Deduplicate, sort newest-first, and render all
    seen = set()
    unique_items = []
    for it in all_items:
        try:
            ts = str(it.get('timestamp') or '').strip()
            victims_list = it.get('victims') if isinstance(it.get('victims'), list) else []
            key = (ts, tuple(victims_list), (it.get('game_mode') or '').upper())
            if key in seen:
                continue
            seen.add(key)
            unique_items.append(it)
        except Exception:
            continue

    sorted_items = sorted(unique_items, key=lambda it: (_parse_ts(str(it.get('timestamp') or '')) or datetime.fromtimestamp(0, tz=timezone.utc)), reverse=True)

    # Log a few samples if location/coordinates appear missing to help debugging
    missing_loc_samples = 0
    for rec in sorted_items:
        try:
            victims = rec.get('victims') if isinstance(rec.get('victims'), list) else []
            title = victims[0] if victims else 'Unknown Victim'
            ship_killed = rec.get('ship_killed')
            is_fps = isinstance(ship_killed, str) and ship_killed.strip().upper() == 'FPS'
            icon = getattr(app, 'icon_rifle', None) if is_fps else getattr(app, 'icon_ship', None)
            accent = '#ff5555' if is_fps else '#3b82f6'
            ship_used = rec.get('ship_used') or 'N/A'
            game_mode = rec.get('game_mode') or 'Unknown Mode'
            ts = rec.get('timestamp') or ''
            secondary = f"{game_mode}  |  {ship_killed or 'Ship'}  |   {ts}"
            # Include location and coordinates when available; fall back gracefully
            location = rec.get('location') or rec.get('zone') or 'Unknown Location'
            coords = rec.get('coordinates') or rec.get('coords') or ''

            # If location/coords are missing, log a couple of samples to inspect incoming data
            try:
                if ((not rec.get('location') and not rec.get('zone')) or not (rec.get('coordinates') or rec.get('coords'))):
                    if missing_loc_samples < 3:
                        keys_preview = ', '.join(list(rec.keys())[:15])
                        global_variables.log(f"[DetailsWindow] Missing location/coords for record — ts={rec.get('timestamp')}, mode={rec.get('game_mode')}, keys=[{keys_preview}]")
                        # Log the full record repr for deep inspection
                        global_variables.log(f"[DetailsWindow] Record sample: {repr(rec)}")
                        missing_loc_samples += 1
            except Exception:
                pass
            if coords and isinstance(coords, str):
                coords_text = coords
            else:
                coords_text = ''
            if coords_text:
                meta = f"Location: {location}  |  Coords: {coords_text}"
            else:
                meta = f"Location: {location}"
            border = '#c9b037' if _is_recent(str(ts)) else None
            _add_card(all_col['container'], title, secondary, meta, icon, accent, border)
        except Exception:
            continue

    # Close button
    btn_frame = tk.Frame(win, bg="#1a1a1a")
    btn_frame.pack(fill=tk.X, padx=8, pady=(4, 8))
    try:
        style = getattr(app, 'BUTTON_STYLE', {})
    except Exception:
        style = {}
    tk.Button(btn_frame, text="Close", command=win.destroy, **style).pack(side=tk.RIGHT)
