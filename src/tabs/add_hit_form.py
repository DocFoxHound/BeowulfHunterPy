import tkinter as tk
from typing import Any, Dict, List
import threading

try:
    # When imported as 'src.tabs.add_hit_form'
    from .. import ironpoint_api  # type: ignore
    from .. import theme  # type: ignore
    import global_variables as gv  # type: ignore
except Exception:
    # When imported as 'tabs.add_hit_form'
    import ironpoint_api  # type: ignore
    import theme  # type: ignore
    import global_variables as gv  # type: ignore

COLORS = {
    'bg': '#1a1a1a',
    'fg': '#ffffff',
    'muted': '#bcbcd8',
    'border': '#2a2a2a',
    'card_bg': '#0f0f0f',
    'accent': '#ff5555',
    'gold': '#DAA520',
}


def open_add_new(parent: tk.Misc) -> None:
    """Open the Add New Pirate Hit form as a Toplevel modal-like window."""
    btn_style = getattr(theme, 'BUTTON_STYLE', {
        "bg": "#0f0f0f",
        "fg": "#ff5555",
        "activebackground": "#330000",
        "activeforeground": "#ffffff",
        "relief": "ridge",
        "bd": 2,
        "font": ("Times New Roman", 12),
    })

    win = tk.Toplevel(parent)
    win.title("Add New Pirate Hit")
    try:
        win.configure(bg=COLORS['bg'])
        win.transient(parent)
        win.grab_set()
    except Exception:
        pass

    form = tk.Frame(win, bg=COLORS['bg'])
    form.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
    actions = tk.Frame(win, bg=COLORS['bg'])
    actions.pack(fill=tk.X, padx=10, pady=(0, 10))

    # Helper to make focus more visible (caret + focus ring)
    def _apply_focus_style(widget: tk.Misc):
        try:
            widget.configure(
                highlightthickness=1,
                highlightbackground=COLORS['border'],
                highlightcolor=COLORS['gold'],
            )
        except Exception:
            pass
        # Make the caret highly visible where supported (Entry/Text)
        try:
            widget.configure(insertbackground=COLORS['fg'])
        except Exception:
            pass
        try:
            widget.configure(insertwidth=2)
        except Exception:
            pass
        def _on_in(_e=None):
            try:
                widget.configure(highlightthickness=2)
            except Exception:
                pass
        def _on_out(_e=None):
            try:
                widget.configure(highlightthickness=1)
            except Exception:
                pass
        try:
            widget.bind('<FocusIn>', _on_in)
            widget.bind('<FocusOut>', _on_out)
        except Exception:
            pass

    # 1. Title (inline with label)
    title_var = tk.StringVar()

    for i in range(2):
        try:
            form.grid_columnconfigure(i, weight=1)
        except Exception:
            pass
    row_idx = 0

    tk.Label(form, text="Title", fg=COLORS['fg'], bg=COLORS['bg']).grid(row=row_idx, column=0, sticky='w', pady=(4, 2))
    title_entry = tk.Entry(form, textvariable=title_var, bg=COLORS['card_bg'], fg=COLORS['fg'])
    title_entry.grid(row=row_idx, column=1, sticky='ew', pady=(4, 2))
    _apply_focus_style(title_entry)
    row_idx += 1

    # 2. Gang dropdown
    tk.Label(form, text="Gang", fg=COLORS['fg'], bg=COLORS['bg']).grid(row=row_idx, column=0, sticky='w', pady=(4, 2))
    gang_var = tk.StringVar(value="None")
    gang_menu = tk.OptionMenu(form, gang_var, "None")
    try:
        gang_menu.configure(bg=COLORS['card_bg'], fg=COLORS['fg'], highlightthickness=1)
    except Exception:
        pass
    gang_menu.grid(row=row_idx, column=1, sticky='ew', pady=(4, 2))
    row_idx += 1

    # 3. Crew Members (text box with autocomplete + selected list)
    tk.Label(form, text="Crew Members", fg=COLORS['fg'], bg=COLORS['bg']).grid(row=row_idx, column=0, sticky='nw')
    crew_frame = tk.Frame(form, bg=COLORS['bg'])
    crew_frame.grid(row=row_idx, column=1, sticky='nsew')
    try:
        # Do not let the crew row expand; this keeps the area tight when empty
        form.grid_rowconfigure(row_idx, weight=0)
    except Exception:
        pass
    row_idx += 1

    crew_name_var = tk.StringVar()
    crew_entry = tk.Entry(crew_frame, textvariable=crew_name_var, bg=COLORS['card_bg'], fg=COLORS['fg'])
    crew_entry.pack(fill=tk.X, pady=(0, 2))
    _apply_focus_style(crew_entry)
    # Chips container for selected crew (box-like elements with remove X)
    crew_chips_container = tk.Frame(crew_frame, bg=COLORS['bg'])
    # Start collapsed
    crew_chips_container.pack(fill=tk.BOTH, expand=False, pady=(0, 0))

    def _update_crew_chips_container_pack():
        try:
            # Expand only if there are any children (chips)
            has_children = bool(crew_chips_container.winfo_children())
            crew_chips_container.pack_configure(fill=tk.BOTH, expand=has_children, pady=(4, 2) if has_children else (0, 0))
        except Exception:
            pass

    # 4. Cargo (single item; name entry autocompletes + qty + price)
    tk.Label(form, text="Cargo", fg=COLORS['fg'], bg=COLORS['bg']).grid(row=row_idx, column=0, sticky='nw', pady=(6, 2))
    cargo_frame = tk.Frame(form, bg=COLORS['bg'])
    cargo_frame.grid(row=row_idx, column=1, sticky='nsew')
    try:
        form.grid_rowconfigure(row_idx, weight=1)
    except Exception:
        pass
    row_idx += 1

    cargo_name_var = tk.StringVar()
    cargo_entry = tk.Entry(cargo_frame, textvariable=cargo_name_var, bg=COLORS['card_bg'], fg=COLORS['fg'])
    cargo_entry.pack(fill=tk.X, pady=(0, 2))
    _apply_focus_style(cargo_entry)
    # Cargo items list container (each with name, qty, price and remove)
    cargo_items_label = tk.Label(cargo_frame, text="Items", fg=COLORS['fg'], bg=COLORS['bg'])
    cargo_items_label.pack(anchor='w', pady=(6, 2))
    cargo_items_container = tk.Frame(cargo_frame, bg=COLORS['bg'])
    cargo_items_container.pack(fill=tk.BOTH, expand=True)

    # 5. Story
    tk.Label(form, text="Story", fg=COLORS['fg'], bg=COLORS['bg']).grid(row=row_idx, column=0, sticky='nw')
    story_text = tk.Text(form, height=5, bg=COLORS['card_bg'], fg=COLORS['fg'], wrap=tk.WORD)
    story_text.grid(row=row_idx, column=1, sticky='nsew')
    _apply_focus_style(story_text)
    try:
        form.grid_rowconfigure(row_idx, weight=1)
    except Exception:
        pass
    row_idx += 1

    # 6. Video link
    tk.Label(form, text="Video Link", fg=COLORS['fg'], bg=COLORS['bg']).grid(row=row_idx, column=0, sticky='w', pady=(6, 2))
    video_var = tk.StringVar()
    video_entry = tk.Entry(form, textvariable=video_var, bg=COLORS['card_bg'], fg=COLORS['fg'])
    video_entry.grid(row=row_idx, column=1, sticky='ew', pady=(6, 2))
    _apply_focus_style(video_entry)
    row_idx += 1

    # Data containers
    all_users: List[Dict[str, str]] = []  # [{id, name}]
    all_commodities: List[str] = []
    commodities_full: List[Dict[str, Any]] = []
    commodity_to_price: Dict[str, float] = {}
    recent_fleets: List[Dict[str, Any]] = []
    gang_display_to_fleet: Dict[str, Dict[str, Any]] = {}
    selected_crew_names: List[str] = []
    cargo_rows: List[Dict[str, Any]] = []

    # Crew inline autocomplete (caret-aware, non-intrusive)
    _auto_flags = {"crew": False, "cargo": False}

    def _crew_autocomplete(*_):
        if _auto_flags["crew"]:
            return
        try:
            text = crew_name_var.get()
            if not text:
                return
            try:
                pos = crew_entry.index(tk.INSERT)
            except Exception:
                pos = len(text)
            prefix = text[:pos]
            if not prefix:
                return
            best = None
            pl = prefix.lower()
            for u in all_users:
                nm = u.get('name', '')
                if nm and nm not in selected_crew_names and nm.lower().startswith(pl):
                    best = nm
                    break
            if not best or best == text:
                return
            _auto_flags["crew"] = True
            try:
                crew_entry.delete(0, tk.END)
                crew_entry.insert(0, best)
                # Keep caret at end of the original prefix; select the suggested suffix
                crew_entry.icursor(len(prefix))
                try:
                    crew_entry.select_range(len(prefix), tk.END)
                except Exception:
                    pass
            finally:
                _auto_flags["crew"] = False
        except Exception:
            _auto_flags["crew"] = False
    crew_name_var.trace_add('write', _crew_autocomplete)

    def _add_crew_chip(name: str):
        try:
            # Build a small chip with name + red X
            chip = tk.Frame(crew_chips_container, bg=COLORS['card_bg'], highlightthickness=1, highlightbackground=COLORS['border'])
            nm_lbl = tk.Label(chip, text=name, fg=COLORS['fg'], bg=COLORS['card_bg'])
            nm_lbl.pack(side=tk.LEFT, padx=(6, 4), pady=2)
            def _remove():
                try:
                    if name in selected_crew_names:
                        selected_crew_names.remove(name)
                except Exception:
                    pass
                try:
                    chip.destroy()
                except Exception:
                    pass
            rm_btn = tk.Button(chip, text='✕', fg='#ffffff', bg=COLORS['accent'], activebackground='#7a0000', relief='flat', padx=6, pady=0, command=_remove)
            rm_btn.pack(side=tk.RIGHT, padx=(0, 4))
            chip.pack(side=tk.TOP, anchor='w', pady=2)
        except Exception:
            pass

    def _crew_add_current(_evt=None):
        try:
            name = crew_name_var.get().strip()
            if not name:
                return
            names = {u.get('name'): u.get('id') for u in all_users}
            if name not in names:
                return
            if name in selected_crew_names:
                return
            selected_crew_names.append(name)
            _add_crew_chip(name)
            crew_name_var.set('')
            _update_crew_chips_container_pack()
        except Exception:
            pass
    crew_entry.bind('<Return>', _crew_add_current)

    # chip removal handled per-chip

    # Cargo inline autocomplete (caret-aware, non-intrusive)
    def _cargo_autocomplete(*_):
        if _auto_flags["cargo"]:
            return
        try:
            text = cargo_name_var.get() or ""
            if not text:
                return
            try:
                pos = cargo_entry.index(tk.INSERT)
            except Exception:
                pos = len(text)
            prefix = text[:pos]
            if not prefix:
                return
            pl = prefix.lower()
            best = None
            for nm in all_commodities:
                if nm and nm.lower().startswith(pl):
                    best = nm
                    break
            if not best or best == text:
                return
            _auto_flags["cargo"] = True
            try:
                cargo_entry.delete(0, tk.END)
                cargo_entry.insert(0, best)
                cargo_entry.icursor(len(prefix))
                try:
                    cargo_entry.select_range(len(prefix), tk.END)
                except Exception:
                    pass
            finally:
                _auto_flags["cargo"] = False
        except Exception:
            _auto_flags["cargo"] = False
    cargo_name_var.trace_add('write', _cargo_autocomplete)

    def _add_cargo_row(_evt=None):
        try:
            name = (cargo_name_var.get() or '').strip()
            if not name:
                return
            # Default quantity and price on add; allow editing in the list rows
            q = 1
            try:
                pr = float(commodity_to_price.get(name, 0) or 0)
            except Exception:
                pr = 0.0
            row = tk.Frame(cargo_items_container, bg=COLORS['bg'])
            row.pack(fill=tk.X, pady=2)
            nm_lbl = tk.Label(row, text=name, fg=COLORS['fg'], bg=COLORS['bg'])
            nm_lbl.pack(side=tk.LEFT)
            tk.Label(row, text='  Qty', fg=COLORS['fg'], bg=COLORS['bg']).pack(side=tk.LEFT)
            q_var = tk.StringVar(value=str(q))
            q_entry = tk.Entry(row, textvariable=q_var, width=6, bg=COLORS['card_bg'], fg=COLORS['fg'])
            q_entry.pack(side=tk.LEFT, padx=(4, 8))
            tk.Label(row, text='Price', fg=COLORS['fg'], bg=COLORS['bg']).pack(side=tk.LEFT)
            pr_var = tk.StringVar(value=(str(int(pr)) if pr == int(pr) else str(pr)))
            pr_entry = tk.Entry(row, textvariable=pr_var, width=10, bg=COLORS['card_bg'], fg=COLORS['fg'])
            pr_entry.pack(side=tk.LEFT, padx=(4, 8))
            rem_btn = tk.Button(row, text='✕', bg=COLORS['card_bg'], fg=COLORS['fg'], relief='ridge')
            rem_btn.pack(side=tk.RIGHT)

            rec = {"frame": row, "name": name, "qty_var": q_var, "price_var": pr_var}
            cargo_rows.append(rec)

            def _remove_this():
                try:
                    cargo_rows.remove(rec)
                except Exception:
                    pass
                try:
                    row.destroy()
                except Exception:
                    pass
            rem_btn.configure(command=_remove_this)

            # Reset inputs
            cargo_name_var.set('')
            try:
                cargo_entry.focus_set()
            except Exception:
                pass
        except Exception:
            pass

    # Press Enter on the cargo name to add the item
    cargo_entry.bind('<Return>', _add_cargo_row)

    # no multi-row cargo UI

    # When a gang is selected, add all of its users as crew chips
    def _on_gang_changed(*_):
        try:
            sel = (gang_var.get() or '').strip()
            if not sel or sel == 'None':
                return
            fleet = gang_display_to_fleet.get(sel)
            if not fleet:
                return
            users = fleet.get('users') or []
            # Build id->display name map from all_users
            id_to_name = {}
            try:
                id_to_name = {str(u.get('id')): str(u.get('name')) for u in (all_users or []) if u.get('id') and u.get('name')}
            except Exception:
                id_to_name = {}
            for u in users:
                try:
                    uid = str(u.get('id') or '')
                    disp = id_to_name.get(uid) or str(u.get('nickname') or u.get('username') or uid)
                    if not disp:
                        continue
                    if disp in selected_crew_names:
                        continue
                    selected_crew_names.append(disp)
                    _add_crew_chip(disp)
                except Exception:
                    continue
            _update_crew_chips_container_pack()
        except Exception:
            pass

    try:
        gang_var.trace_add('write', _on_gang_changed)
    except Exception:
        pass

    def _load_gangs_ui(fleets: List[Dict[str, Any]]):
        try:
            options: List[str] = []
            gang_display_to_fleet.clear()
            for f in fleets:
                try:
                    chan = str(f.get('channel_name') or '')
                    ts = str(f.get('timestamp') or f.get('created_at') or '')
                    disp = chan if chan else (f.get('id') or 'Unknown')
                    if ts:
                        disp = f"{disp} — {ts}"
                    options.append(disp)
                    gang_display_to_fleet[disp] = f
                except Exception:
                    continue
            menu = gang_menu['menu']
            menu.delete(0, 'end')
            # Always prepend 'None' option at top
            options = ["None"] + options
            gang_var.set("None")
            for opt in options:
                menu.add_command(label=opt, command=lambda v=opt: gang_var.set(v))
        except Exception:
            pass


    def _load_data_worker():
        nonlocal all_users, all_commodities, commodities_full, commodity_to_price, recent_fleets
        try:
            recent_fleets = ironpoint_api.get_recent_fleets(10)
        except Exception:
            recent_fleets = []
        try:
            all_users = ironpoint_api.get_all_user_display_options()
        except Exception:
            all_users = []
        try:
            all_commodities = ironpoint_api.get_commodity_names()
            try:
                commodities_full = ironpoint_api.get_commodities_full()
                commodity_to_price = {}
                for it in (commodities_full or []):
                    try:
                        nm = str(it.get('commodity_name') or '').strip()
                        if not nm:
                            continue
                        buy = float(it.get('price_buy_avg') or 0)
                        sell = float(it.get('price_sell_avg') or 0)
                        commodity_to_price[nm] = max(buy, sell)
                    except Exception:
                        continue
            except Exception:
                commodities_full = []
                commodity_to_price = {}
        except Exception:
            all_commodities = []
        try:
            win.after(0, _load_gangs_ui, recent_fleets)
        except Exception:
            pass

    threading.Thread(target=_load_data_worker, daemon=True).start()

    def _on_save():
        """Gather form inputs, build payload, and POST to hittracker asynchronously."""
        try:
            title = (title_var.get() or '').strip()
            gang = (gang_var.get() or '').strip()
            selected_names = list(selected_crew_names)
            name_to_id = {u.get('name'): u.get('id') for u in all_users}
            # assists (ids) and assists_usernames aligned order (excluding current user for now)
            assists_ids: List[str] = []
            assists_usernames: List[str] = []
            for nm in selected_names:
                uid = name_to_id.get(nm)
                if uid:
                    assists_ids.append(str(uid))
                    assists_usernames.append(str(nm))
            # guests are those not matched to a known user id
            guests = [str(nm) for nm in selected_names if name_to_id.get(nm) is None]

            # cargo as array of {commodity_name, scuAmount, avg_price}
            cargo_items: List[Dict[str, Any]] = []
            total_value = 0.0
            total_scu = 0
            for rec in list(cargo_rows):
                try:
                    nm = rec.get('name')
                    q_raw = (rec.get('qty_var') or tk.StringVar()).get() or '0'
                    p_raw = (rec.get('price_var') or tk.StringVar()).get() or '0'
                    q = int(float(q_raw))  # be lenient with user input
                    pr = float(p_raw)
                    cargo_items.append({"commodity_name": nm, "scuAmount": q, "avg_price": int(pr) if pr == int(pr) else pr})
                    total_value += q * pr
                    total_scu += q
                except Exception:
                    continue

            story = (story_text.get("1.0", tk.END) or '').strip()
            video = (video_var.get() or '').strip()

            # Determine patch version
            try:
                patch = gv.get_patch_version() or ironpoint_api.get_latest_patch_version() or ""
            except Exception:
                patch = ""

            # Determine fleet info
            fleet_obj = gang_display_to_fleet.get(gang, {}) if gang and gang != 'None' else {}
            fleet_activity = bool(fleet_obj)
            fleet_ids = []
            try:
                if fleet_obj:
                    # backend may expect id strings; keep as list
                    fid = fleet_obj.get('id')
                    if fid is not None:
                        fleet_ids = [str(fid)]
            except Exception:
                fleet_ids = []

            # Resolve current user id and username
            try:
                current_user_id = str(gv.get_user_id() or "")
            except Exception:
                current_user_id = ""
            try:
                username = ironpoint_api.get_user_display_name_fallback(current_user_id) if current_user_id else (gv.get_rsi_handle() or "")
            except Exception:
                try:
                    username = gv.get_rsi_handle() or ""
                except Exception:
                    username = ""

            # Ensure the current user is the first assist (no duplicates)
            if current_user_id:
                try:
                    if current_user_id in assists_ids:
                        idx = assists_ids.index(current_user_id)
                        assists_ids.pop(idx)
                        try:
                            assists_usernames.pop(idx)
                        except Exception:
                            pass
                    display_name = username or current_user_id
                    assists_ids.insert(0, current_user_id)
                    assists_usernames.insert(0, str(display_name))
                except Exception:
                    # If anything goes wrong, at least prepend id
                    try:
                        if current_user_id not in assists_ids:
                            assists_ids.insert(0, current_user_id)
                            assists_usernames.insert(0, str(username or current_user_id))
                    except Exception:
                        pass

            # Required fields
            import time, datetime as _dt
            now_ms = int(time.time() * 1000)  # id
            # ISO timestamp with milliseconds and Z suffix
            try:
                timestamp_iso = _dt.datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
            except TypeError:
                # Fallback if timespec unsupported: compute manually
                ts = _dt.datetime.utcnow()
                ms = int(ts.microsecond / 1000)
                timestamp_iso = ts.replace(microsecond=0).isoformat() + f".{ms:03d}Z"
            assists_count = len(assists_ids) if assists_ids else 1  # avoid div by zero
            total_value_int = int(round(total_value))
            total_cut_value = int(round(total_value / assists_count)) if assists_count else 0
            total_cut_scu = int(round(total_scu / assists_count)) if assists_count else 0

            payload = {
                "id": str(now_ms),
                "user_id": current_user_id,
                "cargo": cargo_items,
                "total_value": total_value_int,
                "patch": str(patch) if patch else "",
                "total_cut_value": total_cut_value,
                "assists": assists_ids,
                "total_scu": total_scu,
                "air_or_ground": "mixed",
                "title": title,
                "story": story,
                "timestamp": timestamp_iso,
                "username": username,
                "assists_usernames": assists_usernames,
                "video_link": video,
                "additional_media_links": [],
                "type_of_piracy": "Brute Force",
                "fleet_activity": fleet_activity,
                "fleet_ids": fleet_ids,
                "victims": [],
                # thread_id assigned by backend later
                "guests": guests,
                "total_cut_scu": total_cut_scu,
            }

            # Basic validation
            if not title:
                gv.log("Please enter a title before saving.")
                return
            if not current_user_id:
                gv.log("No user_id set. Please validate your key first.")
                return

            def _submit():
                try:
                    ok, info = ironpoint_api.post_hittracker(payload, return_error=True)
                    if ok:
                        gv.log("Hit submitted successfully.")
                        # Refresh latest pirate hits on Piracy tab
                        try:
                            latest = ironpoint_api.get_latest_pirate_hits()
                        except Exception:
                            latest = []
                        try:
                            app = gv.get_app()
                            if app is not None:
                                refs = getattr(app, 'piracy_tab_refs', {})
                                setter = refs.get('set_pirate_hit_cards') if isinstance(refs, dict) else None
                                if callable(setter):
                                    try:
                                        app.after(0, setter, latest)
                                    except Exception:
                                        setter(latest)
                        except Exception:
                            pass
                    else:
                        # Log a clear, human-readable error
                        try:
                            status = (info or {}).get('status')
                            msg = (info or {}).get('message') or 'Request failed'
                            resp_snippet = (info or {}).get('response')
                            err_ex = (info or {}).get('exception')
                            parts = [f"Failed to submit hit. Status: {status}"] if status is not None else ["Failed to submit hit."]
                            parts.append(f"Reason: {msg}")
                            if err_ex:
                                parts.append(f"Exception: {err_ex}")
                            if resp_snippet:
                                parts.append(f"Response: {str(resp_snippet)[:500]}")
                            gv.log(" ".join(parts))
                        except Exception:
                            try:
                                gv.log(f"Failed to submit hit: {info}")
                            except Exception:
                                pass
                except Exception as e:
                    try:
                        gv.log(f"Exception submitting hit: {e}")
                    except Exception:
                        pass

            threading.Thread(target=_submit, daemon=True).start()
            try:
                fid = (fleet_obj or {}).get('id', '')
                gv.log(f"Submitting hit: title='{title}', patch='{patch}', gang='{gang}', gang_id='{fid}', total_value={int(total_value)}, assists={assists_ids}, cargo_items={cargo_items}")
            except Exception:
                pass
            win.destroy()
        except Exception:
            try:
                gv.log("AddNew: failed to gather form data")
            except Exception:
                pass

    def _on_cancel():
        try:
            win.destroy()
        except Exception:
            pass

    save_btn = tk.Button(actions, text="Save", command=_on_save, **btn_style)
    save_btn.pack(side=tk.RIGHT, padx=(6, 0))
    cancel_btn = tk.Button(actions, text="Cancel", command=_on_cancel, **btn_style)
    cancel_btn.pack(side=tk.RIGHT)

    try:
        title_entry.focus_set()
    except Exception:
        pass
