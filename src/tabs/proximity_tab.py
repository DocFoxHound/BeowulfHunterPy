import tkinter as tk
from tkinter import filedialog
from typing import Dict, Any, Optional
import time as _t

import global_variables as gv

try:
    from .. import keys  # type: ignore
except Exception:
    import keys  # type: ignore

COLORS = {
    'bg': '#1a1a1a',
    'fg': '#ffffff',
    'muted': '#bcbcd8',
    'border': '#2a2a2a',
    'card_bg': '#0f0f0f',
    'accent': '#ff5555',
}


def build(parent: tk.Misc) -> Dict[str, Any]:
    refs: Dict[str, Any] = {}

    # Header
    tk.Label(parent, text="Proximity", fg=COLORS['muted'], bg=COLORS['bg'], font=("Times New Roman", 12)).pack(anchor='nw', padx=6, pady=(6, 4))

    # Container for reports + controls
    container = tk.Frame(parent, bg=COLORS['bg'], highlightthickness=1, highlightbackground=COLORS['border'])
    container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(0,6))
    try:
        container.grid_columnconfigure(0, weight=70)
        container.grid_columnconfigure(1, weight=30, minsize=260)
        container.grid_rowconfigure(0, weight=1)
    except Exception:
        pass

    # Reports area (similar to Main tab's Proximity Reports)
    prox_bg = "#0a0a0a"
    reports_outer = tk.Frame(container, bg=prox_bg)
    reports_outer.grid(row=0, column=0, sticky='nsew', padx=(6,3), pady=6)

    header_row = tk.Frame(reports_outer, bg=prox_bg)
    header_row.pack(side=tk.TOP, fill=tk.X)
    tk.Label(header_row, text="Proximity Reports", font=("Times New Roman", 14, "bold"), fg="#ffffff", bg=prox_bg).pack(side=tk.LEFT, padx=4)

    # Removed testing buttons: Test Interdict and Test Nearby

    # Scroll list
    list_container = tk.Frame(reports_outer, bg=prox_bg)
    list_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    canvas = tk.Canvas(list_container, bg=prox_bg, highlightthickness=0, bd=0, height=100)
    vbar = tk.Scrollbar(list_container, orient='vertical', command=canvas.yview)
    canvas.configure(yscrollcommand=vbar.set)
    inner = tk.Frame(canvas, bg=prox_bg)
    win_id = canvas.create_window((0,0), window=inner, anchor='nw')

    def _upd(_evt=None):
        try:
            canvas.configure(scrollregion=canvas.bbox('all'))
        except Exception:
            pass
    def _resize(evt):
        try:
            canvas.itemconfig(win_id, width=evt.width)
        except Exception:
            pass
    inner.bind('<Configure>', _upd)
    canvas.bind('<Configure>', _resize)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _add_card(kind: str, player: str, ship: Optional[str] = None, pinned_until: Optional[float] = None):
        colors = {'bg': '#070707', 'fg': '#ffffff', 'accent': '#ff5555'}
        card = tk.Frame(inner, bg=colors['bg'], highlightthickness=1, highlightbackground='#1f1f1f')
        bar_color = '#3b82f6' if kind == 'actor_stall' else colors['accent']
        tk.Frame(card, bg=bar_color, width=2).pack(side=tk.LEFT, fill=tk.Y)
        if kind == 'actor_stall':
            text = f"Nearby — {player}"
        else:
            # Fake hit / Interdiction
            try:
                evs = gv.get_fake_hit_events() or []
                ctx = None
                for e in evs:
                    if e.get('player') == player and e.get('ship') == ship:
                        ctx = e; break
                from_p = ctx.get('from_player') if isinstance(ctx, dict) else None
                target_p = ctx.get('target_player') if isinstance(ctx, dict) else player
            except Exception:
                from_p = None; target_p = player
            suffix = f" ({ship})" if ship else ""
            text = f"Interdicted — {from_p} → {target_p}{suffix}" if from_p else f"Interdicted — {player}{suffix}"
        tk.Label(card, text=text, font=("Times New Roman", 10), fg=colors['fg'], bg=colors['bg']).pack(side=tk.LEFT, padx=4)
        # Insert ordering
        if kind == 'fake_hit':
            ch = list(inner.winfo_children())
            if ch:
                card.pack(fill=tk.X, padx=4, pady=(0,4), before=ch[0])
            else:
                card.pack(fill=tk.X, padx=4, pady=(0,4))
        else:
            card.pack(fill=tk.X, padx=4, pady=(0,4))
        return card

    def refresh_player_events():
        try:
            gv.prune_expired_fake_hit_events(_t.time())
        except Exception:
            pass
        # Peek at events after pruning; if none, avoid clearing existing UI to prevent a blank state
        try:
            fe = list(gv.get_fake_hit_events() or [])
        except Exception:
            fe = []
        try:
            se = list(gv.get_actor_stall_events() or [])
        except Exception:
            se = []
        try:
            if not fe and not se:
                # No events to show; keep current cards to avoid an empty flash
                return
        except Exception:
            pass
        # Clear and rebuild when there is something to render
        try:
            for ch in list(inner.winfo_children()):
                ch.destroy()
        except Exception:
            pass
        try:
            fe.reverse()
            for ev in fe:
                _add_card('fake_hit', ev.get('player'), ev.get('ship'), pinned_until=ev.get('expires_at'))
            se.reverse()
            for ev in se:
                _add_card('actor_stall', ev.get('player'))
        except Exception:
            pass

    refs['refresh_player_events'] = refresh_player_events
    # Register these refs globally so parser-driven updates can refresh this tab
    try:
        gv.set_proximity_tab_refs(refs)
    except Exception:
        pass

    # Settings area
    settings = tk.Frame(container, bg=COLORS['bg'])
    settings.grid(row=0, column=1, sticky='nsew', padx=(3,6), pady=6)

    tk.Label(settings, text="Sounds", fg=COLORS['fg'], bg=COLORS['bg'], font=("Times New Roman", 12, "bold")).pack(anchor='w', pady=(0,4))

    def _pick_snare():
        path = filedialog.askopenfilename(parent=parent, title="Choose Snare Sound", filetypes=[("WAV files", "*.wav;*.wave"), ("All files", "*.*")])
        if not path:
            return
        try:
            keys.update_sound_paths(interdiction_path=path, nearby_path=keys.get_custom_sound_nearby(), kill_path=keys.get_custom_sound_kill())
            gv.set_custom_sound_interdiction(path)
            gv.log(f"Custom Snare sound set: {path}")
        except Exception:
            pass

    def _pick_proximity():
        path = filedialog.askopenfilename(parent=parent, title="Choose Proximity Sound", filetypes=[("WAV files", "*.wav;*.wave"), ("All files", "*.*")])
        if not path:
            return
        try:
            keys.update_sound_paths(interdiction_path=keys.get_custom_sound_interdiction(), nearby_path=path, kill_path=keys.get_custom_sound_kill())
            gv.set_custom_sound_nearby(path)
            gv.log(f"Custom Proximity sound set: {path}")
        except Exception:
            pass

    def _pick_kill():
        path = filedialog.askopenfilename(parent=parent, title="Choose Kill Sound", filetypes=[("WAV files", "*.wav;*.wave"), ("All files", "*.*")])
        if not path:
            return
        try:
            keys.update_sound_paths(interdiction_path=keys.get_custom_sound_interdiction(), nearby_path=keys.get_custom_sound_nearby(), kill_path=path)
            gv.set_custom_sound_kill(path)
            gv.log(f"Custom Kill sound set: {path}")
        except Exception:
            pass

    btn_style = getattr(gv.get_app(), 'BUTTON_STYLE', {}) if gv.get_app() else {"bg":"#0f0f0f","fg":"#ff5555","activebackground":"#330000","activeforeground":"#ffffff","relief":"ridge","bd":2,"font": ("Times New Roman", 12)}
    tk.Button(settings, text="Choose Snare Sound", command=_pick_snare, **btn_style).pack(fill=tk.X, pady=(0,6))
    tk.Button(settings, text="Choose Proximity Sound", command=_pick_proximity, **btn_style).pack(fill=tk.X, pady=(0,6))
    tk.Button(settings, text="Choose Kill Sound", command=_pick_kill, **btn_style).pack(fill=tk.X, pady=(0,10))

    # Toggles
    tk.Label(settings, text="Notices & Sounds", fg=COLORS['fg'], bg=COLORS['bg'], font=("Times New Roman", 12, "bold")).pack(anchor='w', pady=(0,4))
    var_play_kill = tk.BooleanVar(value=gv.get_play_kill_sound())
    var_show_kill = tk.BooleanVar(value=gv.get_show_kill_notice())
    var_play_snare = tk.BooleanVar(value=gv.get_play_snare_sound())
    var_show_snare = tk.BooleanVar(value=gv.get_show_snare_notice())
    var_play_prox = tk.BooleanVar(value=gv.get_play_proximity_sound())
    var_show_prox = tk.BooleanVar(value=gv.get_show_proximity_notice())

    def _apply_toggles():
        try:
            gv.set_play_kill_sound(var_play_kill.get())
            gv.set_play_snare_sound(var_play_snare.get())
            gv.set_play_proximity_sound(var_play_prox.get())
            # Show toggles map to overlay filters
            gv.set_show_kill_notice(var_show_kill.get())
            gv.set_show_snare_notice(var_show_snare.get())
            gv.set_show_proximity_notice(var_show_prox.get())
            try:
                from overlay_window import refresh_overlay  # type: ignore
                refresh_overlay()
            except Exception:
                pass
        except Exception:
            pass

    # Place six checkboxes in a compact 3-column layout
    toggles_grid = tk.Frame(settings, bg=COLORS['bg'])
    toggles_grid.pack(fill=tk.X, pady=(0,6))

    def _mk_check(parent, text, var):
        cb = tk.Checkbutton(parent, text=text, variable=var, command=_apply_toggles,
                            bg=COLORS['bg'], fg=COLORS['fg'], selectcolor='#222222',
                            activebackground=COLORS['bg'], activeforeground=COLORS['fg'], highlightthickness=0)
        return cb

    # Column 0: Kill
    cb_kill_sound = _mk_check(toggles_grid, "Kill Sound", var_play_kill)
    cb_kill_notice = _mk_check(toggles_grid, "Kill Notice", var_show_kill)
    cb_kill_sound.grid(row=0, column=0, padx=(0,10), pady=2, sticky='w')
    cb_kill_notice.grid(row=1, column=0, padx=(0,10), pady=2, sticky='w')

    # Column 1: Snare (Interdiction)
    cb_snare_sound = _mk_check(toggles_grid, "Snare Sound", var_play_snare)
    cb_snare_notice = _mk_check(toggles_grid, "Snare Notice", var_show_snare)
    cb_snare_sound.grid(row=0, column=1, padx=(0,10), pady=2, sticky='w')
    cb_snare_notice.grid(row=1, column=1, padx=(0,10), pady=2, sticky='w')

    # Column 2: Proximity (Actor Stall)
    cb_prox_sound = _mk_check(toggles_grid, "Proximity Sound", var_play_prox)
    cb_prox_notice = _mk_check(toggles_grid, "Proximity Notice", var_show_prox)
    cb_prox_sound.grid(row=0, column=2, padx=(0,0), pady=2, sticky='w')
    cb_prox_notice.grid(row=1, column=2, padx=(0,0), pady=2, sticky='w')

    # Overlay controls (copied from Dogfighting)
    ov = tk.Frame(settings, bg=COLORS['bg'])
    ov.pack(fill=tk.X, pady=(10,6))
    tk.Label(ov, text="Overlay", fg=COLORS['fg'], bg=COLORS['bg'], font=("Times New Roman", 12, "bold")).pack(anchor='w', pady=(0,4))
    overlay_status_var = tk.StringVar(value='Enabled' if gv.is_overlay_enabled() else 'Disabled')
    corner_var = tk.StringVar(value=gv.get_overlay_corner())

    def _apply_corner():
        try:
            gv.set_overlay_corner(corner_var.get())
            from overlay_window import refresh_overlay, ensure_overlay  # type: ignore
            ensure_overlay(); refresh_overlay()
        except Exception:
            pass

    def _toggle_overlay():
        try:
            enabled = not gv.is_overlay_enabled()
            gv.set_overlay_enabled(enabled)
            overlay_status_var.set('Enabled' if enabled else 'Disabled')
            if enabled:
                from overlay_window import ensure_overlay, refresh_overlay  # type: ignore
                ensure_overlay(); refresh_overlay()
            else:
                from overlay_window import disable_overlay  # type: ignore
                disable_overlay()
        except Exception:
            pass

    tk.Button(ov, text="Enable/Disable", command=_toggle_overlay, **btn_style).pack(fill=tk.X, pady=(0,4))
    tk.Label(ov, textvariable=overlay_status_var, fg=COLORS['muted'], bg=COLORS['bg'], font=("Times New Roman", 10)).pack(anchor='w', pady=(0,6))

    # Two-column layout for overlay corner selection
    box = tk.Frame(ov, bg=COLORS['bg'])
    box.pack(fill=tk.X)
    # Left column: Top-Left, Bottom-Left; Right column: Top-Right, Bottom-Right
    left_col = tk.Frame(box, bg=COLORS['bg'])
    right_col = tk.Frame(box, bg=COLORS['bg'])
    left_col.pack(side=tk.LEFT, anchor='nw', padx=(0,20))
    right_col.pack(side=tk.LEFT, anchor='nw')

    def _mk_corner(parent, label, val):
        return tk.Radiobutton(parent, text=label, value=val, variable=corner_var,
                              command=_apply_corner, bg=COLORS['bg'], fg=COLORS['fg'], selectcolor='#222222',
                              activebackground=COLORS['bg'], activeforeground=COLORS['fg'], highlightthickness=0, padx=2, pady=2)

    _mk_corner(left_col, 'Top-Left', 'top-left').pack(anchor='w')
    _mk_corner(left_col, 'Bottom-Left', 'bottom-left').pack(anchor='w')
    _mk_corner(right_col, 'Top-Right', 'top-right').pack(anchor='w')
    _mk_corner(right_col, 'Bottom-Right', 'bottom-right').pack(anchor='w')

    # initial fill
    try:
        refresh_player_events()
    except Exception:
        pass

    return refs
