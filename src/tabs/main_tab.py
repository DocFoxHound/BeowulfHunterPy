import os
import io
import threading
import re
from datetime import datetime, timezone, timedelta
import tkinter as tk
from typing import Dict, Any, Optional, Callable
from PIL import Image, ImageTk
import requests
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
        placeholder_avatar = None
        placeholder_org = None
        placeholder_avatar_small = None
        placeholder_org_small = None
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
        # Simple gray placeholder for victim avatars (50x50)
        try:
            _ph = Image.new('RGBA', (50, 50), (40, 40, 40, 255))
            placeholder_avatar = ImageTk.PhotoImage(_ph)
        except Exception:
            placeholder_avatar = None
        # Small gray placeholder for org avatars (25x25)
        try:
            _phs = Image.new('RGBA', (25, 25), (40, 40, 40, 255))
            placeholder_org = ImageTk.PhotoImage(_phs)
        except Exception:
            placeholder_org = None
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
        if placeholder_avatar is not None:
            widgets['placeholder_avatar'] = placeholder_avatar
            try:
                setattr(app, 'placeholder_avatar', placeholder_avatar)
            except Exception:
                pass
        # Create small (16x16) avatar placeholder for proximity reports
        try:
            _ph_small = Image.new('RGBA', (16, 16), (60, 60, 60, 255))
            placeholder_avatar_small = ImageTk.PhotoImage(_ph_small)
            widgets['placeholder_avatar_small'] = placeholder_avatar_small
            try:
                setattr(app, 'placeholder_avatar_small', placeholder_avatar_small)
            except Exception:
                pass
        except Exception:
            placeholder_avatar_small = None
        # Small org placeholder (16x16) distinct shade
        try:
            _ph_org_small = Image.new('RGBA', (16, 16), (80, 80, 80, 255))
            placeholder_org_small = ImageTk.PhotoImage(_ph_org_small)
            widgets['placeholder_org_small'] = placeholder_org_small
            try:
                setattr(app, 'placeholder_org_small', placeholder_org_small)
            except Exception:
                pass
        except Exception:
            placeholder_org_small = None
        if placeholder_org is not None:
            widgets['placeholder_org'] = placeholder_org
            try:
                setattr(app, 'placeholder_org', placeholder_org)
            except Exception:
                pass
    except Exception:
        pass

    # In-memory cache for org avatar images (url -> ImageTk.PhotoImage)
    try:
        if not hasattr(app, 'org_avatar_cache') or not isinstance(getattr(app, 'org_avatar_cache'), dict):
            setattr(app, 'org_avatar_cache', {})
    except Exception:
        pass

    avatar_cache: Dict[str, Any] = getattr(app, 'org_avatar_cache', {})

    # Cache for proximity profile lookups: handle_lower -> {'avatar_img': PhotoImage|None, 'org_img': PhotoImage|None, 'org_name': str|None}
    try:
        if not hasattr(app, 'proximity_profile_cache') or not isinstance(getattr(app, 'proximity_profile_cache'), dict):
            setattr(app, 'proximity_profile_cache', {})
    except Exception:
        pass
    proximity_cache: Dict[str, Any] = getattr(app, 'proximity_profile_cache', {})

    # Simple tooltip helper for widgets
    class _ToolTip:
        def __init__(self, widget: tk.Widget, text: str = ""):
            self.widget = widget
            self.text = text
            self.tip: Optional[tk.Toplevel] = None
            try:
                widget.bind("<Enter>", self._enter)
                widget.bind("<Leave>", self._leave)
                widget.bind("<Motion>", self._motion)
            except Exception:
                pass

        def _enter(self, _evt=None):
            self._show()

        def _leave(self, _evt=None):
            self._hide()

        def _motion(self, evt):
            try:
                if self.tip is not None:
                    # Offset a bit from the cursor
                    x = evt.x_root + 12
                    y = evt.y_root + 12
                    self.tip.wm_geometry(f"+{x}+{y}")
            except Exception:
                pass

        def _show(self):
            if not self.text:
                return
            try:
                if self.tip is not None:
                    return
                tip = tk.Toplevel(self.widget)
                tip.wm_overrideredirect(True)
                tip.attributes('-topmost', True)
                lbl = tk.Label(
                    tip,
                    text=str(self.text),
                    bg="#2a2a2a",
                    fg="#ffffff",
                    relief="solid",
                    borderwidth=1,
                    font=("Times New Roman", 10)
                )
                lbl.pack(ipadx=6, ipady=3)
                # Place near the widget
                try:
                    x = self.widget.winfo_rootx() + 10
                    y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
                    tip.wm_geometry(f"+{x}+{y}")
                except Exception:
                    pass
                self.tip = tip
            except Exception:
                self.tip = None

        def _hide(self):
            try:
                if self.tip is not None:
                    self.tip.destroy()
                    self.tip = None
            except Exception:
                self.tip = None

    def _make_square_thumbnail(img: Image.Image, size: int = 50) -> Image.Image:
        try:
            w, h = img.size
            # center-crop to square
            if w != h:
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                img = img.crop((left, top, left + side, top + side))
            return img.resize((size, size), Image.Resampling.LANCZOS)
        except Exception:
            try:
                return img.resize((size, size), Image.Resampling.LANCZOS)
            except Exception:
                return img

    # Fetch RSI profile details (avatar url, org image url, org name) — minimal HTML parse
    def _fetch_rsi_profile(handle: str, timeout: int = 8):
        if not handle:
            return (None, None, None)
        try:
            h = str(handle).strip()
            url = f"https://robertsspaceindustries.com/en/citizens/{h}"
            headers = {
                "User-Agent": "BeowulfHunter/1.0 (proximity)",
                "Accept": "text/html,application/xhtml+xml",
            }
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code != 200 or not resp.text:
                return (None, None, None)
            html = resp.text
            # Avatar image (same pattern as scraper)
            m_avatar = re.search(r'<span class="title">\s*Profile\s*</span>.*?<img\s+src="([^"]+)"', html, re.IGNORECASE | re.DOTALL)
            # Org image and name under Main organization section
            m_orgimg = re.search(r'<span class="title">\s*Main\s+organization\s*</span>.*?<img\s+src="([^"]+)"', html, re.IGNORECASE | re.DOTALL)
            m_orgname = re.search(r'<span class="title">\s*Main\s+organization\s*</span>.*?<a[^>]*>([^<]+)</a>', html, re.IGNORECASE | re.DOTALL)
            def _abs(u):
                if not u:
                    return None
                return ("https://robertsspaceindustries.com" + u) if u.startswith("/") else u
            avatar_url = _abs(m_avatar.group(1)) if m_avatar else None
            orgimg_url = _abs(m_orgimg.group(1)) if m_orgimg else None
            org_name = m_orgname.group(1).strip() if m_orgname else None
            return (orgimg_url, avatar_url, org_name)
        except Exception:
            return (None, None, None)

    # Download an image and convert to small square PhotoImage
    def _download_photoimage(url: Optional[str], size: int = 16) -> Optional[ImageTk.PhotoImage]:
        if not url:
            return None
        try:
            r = requests.get(url, timeout=8)
            if r.status_code != 200:
                return None
            im = Image.open(io.BytesIO(r.content)).convert('RGBA')
            im = _make_square_thumbnail(im, size)
            return ImageTk.PhotoImage(im)
        except Exception:
            return None

    # Ensure labels show fetched avatar/org images and tooltip of org name
    def _ensure_proximity_profile(avatar_label: tk.Label, org_label: tk.Label, handle: Optional[str]):
        if not handle:
            return
        try:
            key = str(handle).strip().lower()
        except Exception:
            key = None
        if not key:
            return
        # If cached, set immediately
        try:
            cached = proximity_cache.get(key)
            if isinstance(cached, dict):
                av = cached.get('avatar_img')
                og = cached.get('org_img')
                if isinstance(av, ImageTk.PhotoImage):
                    try:
                        avatar_label.configure(image=av)
                        avatar_label.image = av
                    except Exception:
                        pass
                if isinstance(og, ImageTk.PhotoImage):
                    try:
                        org_label.configure(image=og)
                        org_label.image = og
                    except Exception:
                        pass
                # Tooltip
                try:
                    name = cached.get('org_name')
                    if name:
                        _ToolTip(org_label, str(name))
                except Exception:
                    pass
                return
        except Exception:
            pass

        def worker():
            orgimg_url, avatar_url, org_name = _fetch_rsi_profile(handle)
            av_img = _download_photoimage(avatar_url, 16)
            og_img = _download_photoimage(orgimg_url, 16)
            def on_main():
                try:
                    # store in cache
                    try:
                        proximity_cache[key] = {'avatar_img': av_img, 'org_img': og_img, 'org_name': org_name}
                    except Exception:
                        pass
                    if isinstance(av_img, ImageTk.PhotoImage):
                        try:
                            avatar_label.configure(image=av_img)
                            avatar_label.image = av_img
                        except Exception:
                            pass
                    if isinstance(og_img, ImageTk.PhotoImage):
                        try:
                            org_label.configure(image=og_img)
                            org_label.image = og_img
                        except Exception:
                            pass
                    try:
                        if org_name:
                            _ToolTip(org_label, str(org_name))
                    except Exception:
                        pass
                except Exception:
                    pass
            try:
                app.after(0, on_main)
            except Exception:
                try:
                    on_main()
                except Exception:
                    pass
        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            pass

    # Async loader that updates a label with the avatar when ready (parametrized size)
    def _load_avatar_async_sized(label: tk.Label, url: Optional[str], size: int = 50):
        if not url:
            return
        try:
            cache_key = f"{url}#s{int(size)}"
            cached = avatar_cache.get(cache_key)
            if isinstance(cached, ImageTk.PhotoImage):
                try:
                    label.configure(image=cached)
                    label.image = cached
                except Exception:
                    pass
                return
        except Exception:
            pass

        def worker():
            content = None
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    content = resp.content
            except Exception:
                content = None

            def on_main():
                try:
                    if content:
                        try:
                            pil = Image.open(io.BytesIO(content)).convert('RGBA')
                            pil = _make_square_thumbnail(pil, size)
                            photo = ImageTk.PhotoImage(pil)
                            try:
                                avatar_cache[cache_key] = photo
                            except Exception:
                                pass
                            try:
                                label.configure(image=photo)
                                label.image = photo
                            except Exception:
                                pass
                            return
                        except Exception:
                            pass
                    # Fallback: keep placeholder
                except Exception:
                    pass

            try:
                # schedule on the Tk main thread
                app.after(0, on_main)
            except Exception:
                try:
                    on_main()
                except Exception:
                    pass

        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            pass

    # Backwards-compatible wrapper that loads 50px avatars
    def _load_avatar_async(label: tk.Label, url: Optional[str]):
        _load_avatar_async_sized(label, url, 50)

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
        key_center, text="Player Key:", font=("Times New Roman", 12), fg="#ffffff", bg="#1a1a1a"
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

    # Second row: ORG key input
    org_center = tk.Frame(key_section, bg="#1a1a1a")
    org_center.pack(side=tk.TOP, pady=(6, 0))

    org_label = tk.Label(
        org_center, text="ORG Key:", font=("Times New Roman", 12), fg="#ffffff", bg="#1a1a1a"
    )
    org_label.pack(side=tk.LEFT, padx=(0, 8))

    org_key_entry = tk.Entry(
        org_center,
        width=30,
        font=("Times New Roman", 12),
        highlightthickness=2,
        highlightbackground="#ff0000",
        highlightcolor="#ff0000",
        bg="#0a0a0a",
        fg="#ffffff",
        insertbackground="#ff5555"
    )
    org_key_entry.pack(side=tk.LEFT)

    # Activate button (placed below both inputs)
    try:
        act_style = getattr(app, 'BUTTON_STYLE', {})
    except Exception:
        act_style = {}
    button_row = tk.Frame(key_section, bg="#1a1a1a")
    button_row.pack(side=tk.TOP, pady=(10, 0))
    activate_button = tk.Button(button_row, text="Activate", **act_style)
    activate_button.pack()

    # Placeholder for ORG key error (shown only when invalid) inside button row so it doesn't move the button row
    org_error_label = tk.Label(
        button_row,
        text="",
        font=("Times New Roman", 12),
        fg="#ff5555",
        bg="#1a1a1a",
        wraplength=600,
        justify="left",
    )
    # Not packed by default; controller will pack when needed under the Activate button

    # Help/instructions shown when a key is required
    try:
        help_text = (
            "How to get keys:\n"
            "1. Open the IronPoint Discord\n"
            "2. Use /key-create to retrieve both keys\n"
            "3. Paste both keys above, then click Activate"
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
    # --- Player Events (Actor Stall / Fake Hit) area ---
    # Placed above kill columns but below key section elements.
    # Darker background for proximity reports
    prox_bg = "#0a0a0a"  # darker than the main bg
    player_events_outer = tk.Frame(parent, bg=prox_bg)
    # Proximity Reports moved to the Proximity tab; do not pack in Main

    # Header row with title and a temporary Inject Test button on the right
    pe_header_row = tk.Frame(player_events_outer, bg=prox_bg)
    pe_header_row.pack(side=tk.TOP, fill=tk.X)
    pe_header = tk.Label(
        pe_header_row,
        text="Proximity Reports",
        font=("Times New Roman", 14, "bold"),
        fg="#ffffff",
        bg=prox_bg
    )
    pe_header.pack(side=tk.LEFT, padx=4)
    try:
        style = getattr(app, 'BUTTON_STYLE', {})
    except Exception:
        style = {}
    # Removed test buttons (Test Interdict / Test Nearby) from Main tab proximity header

    # Scrollable horizontal frame? Requirement implies vertical list; implement vertical scroll.
    pe_container_frame = tk.Frame(player_events_outer, bg=prox_bg)
    pe_container_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
    # Shorter height (~80px)
    pe_canvas = tk.Canvas(pe_container_frame, bg=prox_bg, highlightthickness=0, bd=0, height=80)
    pe_scroll = tk.Scrollbar(pe_container_frame, orient='vertical', command=pe_canvas.yview)
    pe_canvas.configure(yscrollcommand=pe_scroll.set)
    pe_inner = tk.Frame(pe_canvas, bg=prox_bg)
    pe_window_id = pe_canvas.create_window((0,0), window=pe_inner, anchor='nw')

    def _pe_update_scroll(_evt=None):
        try:
            pe_canvas.configure(scrollregion=pe_canvas.bbox('all'))
        except Exception:
            pass

    def _pe_resize_inner(evt):
        try:
            pe_canvas.itemconfig(pe_window_id, width=evt.width)
        except Exception:
            pass

    pe_inner.bind('<Configure>', _pe_update_scroll)
    pe_canvas.bind('<Configure>', _pe_resize_inner)

    def _pe_on_mousewheel(event):
        try:
            steps = int(-1 * (event.delta / 120)) if event.delta else 0
            if steps:
                pe_canvas.yview_scroll(steps, 'units')
        except Exception:
            pass

    pe_canvas.bind('<Enter>', lambda e: pe_canvas.bind_all('<MouseWheel>', _pe_on_mousewheel))
    pe_canvas.bind('<Leave>', lambda e: pe_canvas.unbind_all('<MouseWheel>'))
    pe_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    pe_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Helper to build a condensed player card
    def _add_player_event_card(kind: str, player: str, ship: Optional[str] = None, pinned_until: Optional[float] = None):
        colors = {
            'bg': '#070707',
            'fg': '#ffffff',
            'muted': '#bcbcd8',
            'accent': '#ff5555',
            'flash_a': '#5a0f0f',
            'flash_b': '#0f0f0f',
        }
        outline = '#1f1f1f'
        card = tk.Frame(pe_inner, bg=colors['bg'], highlightthickness=1, highlightbackground=outline)
        # Minimal accent bar
        bar_color = '#3b82f6' if kind == 'actor_stall' else colors['accent']
        tk.Frame(card, bg=bar_color, width=2).pack(side=tk.LEFT, fill=tk.Y)

        # Tiny avatar (16x16) and org icon (16x16) then single-line text
        try:
            ph_small = getattr(app, 'placeholder_avatar_small', None)
        except Exception:
            ph_small = None
        try:
            ph_org_small = getattr(app, 'placeholder_org_small', None)
        except Exception:
            ph_org_small = None
        av = tk.Label(card, bg=colors['bg'])
        if ph_small is not None:
            try:
                av.configure(image=ph_small)
                av.image = ph_small
            except Exception:
                pass
        av.pack(side=tk.LEFT, padx=(4,2), pady=2)
        og = tk.Label(card, bg=colors['bg'])
        if ph_org_small is not None:
            try:
                og.configure(image=ph_org_small)
                og.image = ph_org_small
            except Exception:
                pass
        og.pack(side=tk.LEFT, padx=(0,4), pady=2)

        # Compose a single concise line
        if kind == 'actor_stall':
            text = f"Nearby — {player}"
        else:
            # Fake hit / Interdiction: show who interdicted whom when available
            # Events now store from_player (interdictor) and player/target.
            try:
                # Attempt to extract richer context from fake hit events list
                evs = global_variables.get_fake_hit_events() or []
                context = None
                for e in evs:
                    if e.get('player') == player and e.get('ship') == ship:
                        context = e
                        break
                from_p = context.get('from_player') if isinstance(context, dict) else None
                target_p = context.get('target_player') if isinstance(context, dict) else player
            except Exception:
                from_p = None
                target_p = player
            suffix = f" ({ship})" if ship else ""
            if from_p and target_p:
                text = f"Interdicted — {from_p} → {target_p}{suffix}"
            else:
                text = f"Interdicted — {player}{suffix}"
        tk.Label(card, text=text, font=("Times New Roman", 10), fg=colors['fg'], bg=colors['bg']).pack(side=tk.LEFT, padx=2)

        # Trigger async fetch for real images and org name tooltip
        try:
            # Prefer interdictor's avatar when available on fake hits; else fall back to player
            handle_for_avatar = player
            if kind == 'fake_hit':
                try:
                    evs = global_variables.get_fake_hit_events() or []
                    ctx = None
                    for e in evs:
                        if e.get('player') == player and e.get('ship') == ship:
                            ctx = e
                            break
                    pref = ctx.get('from_player') if isinstance(ctx, dict) else None
                    if pref:
                        handle_for_avatar = pref
                except Exception:
                    handle_for_avatar = player
            _ensure_proximity_profile(av, og, handle_for_avatar)
        except Exception:
            pass

        # Insert at top respecting pinned fake hit ordering: pinned cards should stay above others.
        if kind == 'fake_hit':
            # Place at absolute top
            try:
                children = list(pe_inner.winfo_children())
                if children:
                    card.pack(fill=tk.X, padx=4, pady=(0,4), before=children[0])
                else:
                    card.pack(fill=tk.X, padx=4, pady=(0,4))
            except Exception:
                card.pack(fill=tk.X, padx=4, pady=(0,4))
        else:
            # Insert after any pinned fake hit cards (those with attribute _pinned=True)
            try:
                children = list(pe_inner.winfo_children())
                insert_before = None
                for child in children:
                    if not getattr(child, '_pinned', False):
                        insert_before = child
                        break
                if insert_before is not None:
                    card.pack(fill=tk.X, padx=4, pady=(0,4), before=insert_before)
                else:
                    card.pack(fill=tk.X, padx=4, pady=(0,4))
            except Exception:
                card.pack(fill=tk.X, padx=4, pady=(0,4))

        # Flashing for fake hit cards
        if kind == 'fake_hit':
            card._pinned = True  # mark pinned
            card._pinned_until = pinned_until or 0
            def _flash_state(state=[False]):
                try:
                    import time as _t
                    now = _t.time()
                    if now >= getattr(card, '_pinned_until', 0):
                        # Stop flashing and unpin
                        card._pinned = False
                        try:
                            card.configure(bg=colors['bg'])
                        except Exception:
                            pass
                        return
                    state[0] = not state[0]
                    new_bg = colors['flash_a'] if state[0] else colors['flash_b']
                    try:
                        card.configure(bg=new_bg)
                        for ch in card.winfo_children():
                            try:
                                ch.configure(bg=new_bg)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        card.after(500, _flash_state)
                    except Exception:
                        pass
                except Exception:
                    pass
            try:
                _flash_state()
            except Exception:
                pass
        return card

    def refresh_player_events():
        """Rebuild player events area from global state (efficient enough given small sizes)."""
        # Prune expired fake hit events first
        try:
            import time as _t
            global_variables.prune_expired_fake_hit_events(_t.time())
        except Exception:
            pass
        # Clear existing cards
        try:
            for ch in list(pe_inner.winfo_children()):
                ch.destroy()
        except Exception:
            pass
        # Fetch events
        try:
            stall_events = global_variables.get_actor_stall_events()
        except Exception:
            stall_events = []
        try:
            fake_events = global_variables.get_fake_hit_events()
        except Exception:
            fake_events = []
        # Render fake hits first (newest last in storage; show newest first)
        try:
            # sort fake events by timestamp descending (string compare fallback)
            fe_sorted = list(fake_events)
            fe_sorted.reverse()
            import time as _t
            now_ts = _t.time()
            for ev in fe_sorted:
                _add_player_event_card('fake_hit', ev.get('player'), ev.get('ship'), pinned_until=ev.get('expires_at'))
            # Then actor stall (newest last -> show newest first underneath pinned region)
            se_sorted = list(stall_events)
            se_sorted.reverse()
            for ev in se_sorted:
                _add_player_event_card('actor_stall', ev.get('player'))
        except Exception:
            pass

    # Expose refresh & add helpers (controllers may push events directly if desired)
    def add_actor_stall_card(player: str):
        return _add_player_event_card('actor_stall', player)

    def add_fake_hit_card(player: str, ship: Optional[str], pinned_until: Optional[float]):
        return _add_player_event_card('fake_hit', player, ship, pinned_until=pinned_until)

    # Initial empty build
    try:
        refresh_player_events()
    except Exception:
        pass

    # Optional: helper to inject test proximity events into globals and refresh UI
    def inject_test_proximity_events():
        try:
            import time as _t
            now = _t.time()
            # Simulate 3 actor stalls and 2 fake hits
            try:
                global_variables.add_actor_stall_event({'timestamp': '2025-11-07T00:00:00Z', 'player': 'TestPilotA'})
                global_variables.add_actor_stall_event({'timestamp': '2025-11-07T00:00:05Z', 'player': 'TestPilotB'})
                global_variables.add_actor_stall_event({'timestamp': '2025-11-07T00:00:10Z', 'player': 'TestPilotC'})
            except Exception:
                pass
            try:
                global_variables.add_fake_hit_event({'timestamp': '2025-11-07T00:01:00Z', 'player': 'InterceptorOne', 'ship': 'ANVL_Glade', 'expires_at': now + 10})
                global_variables.add_fake_hit_event({'timestamp': '2025-11-07T00:01:05Z', 'player': 'Scarecrow_iso', 'ship': 'MISC_Hull_C', 'expires_at': now + 10})
            except Exception:
                pass
            refresh_player_events()
        except Exception:
            pass
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
        org_picture_url: Optional[str] = None,
        victim_image_url: Optional[str] = None,
        org_sid_tooltip: Optional[str] = None,
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
                icon_lbl.pack(side=tk.RIGHT, padx=(8, 8), pady=6)
            except Exception:
                pass

        # Small org image (25x25) to the left of the icon
        try:
            org_lbl = tk.Label(card, bg=colors['card_bg'])
            ph_small = getattr(app, 'placeholder_org', None)
            if ph_small is not None:
                try:
                    org_lbl.configure(image=ph_small)
                    org_lbl.image = ph_small
                except Exception:
                    pass
            # Tooltip with org SID on the org badge
            if org_sid_tooltip:
                try:
                    _ToolTip(org_lbl, str(org_sid_tooltip))
                except Exception:
                    pass
            if isinstance(org_picture_url, str) and org_picture_url.strip():
                _load_avatar_async_sized(org_lbl, org_picture_url.strip(), 25)
            org_lbl.pack(side=tk.RIGHT, padx=(0, 0), pady=6)
        except Exception:
            pass

        # Victim avatar on the left, between accent bar and body
        avatar_label = None
        try:
            placeholder = getattr(app, 'placeholder_avatar', None)
            avatar_label = tk.Label(card, bg=colors['card_bg'])
            if placeholder is not None:
                try:
                    avatar_label.configure(image=placeholder)
                    avatar_label.image = placeholder
                except Exception:
                    pass
            avatar_label.pack(side=tk.LEFT, padx=6, pady=6)
            # Async load victim image from URL
            if isinstance(victim_image_url, str) and victim_image_url.strip():
                _load_avatar_async_sized(avatar_label, victim_image_url.strip(), 50)
        except Exception:
            avatar_label = None

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

    # Processing count label (hidden unless >0)
    processing_label = tk.Label(middle_col, text="", font=("Times New Roman", 11, "bold"), fg="#f5f5f5", bg="#1a1a1a")

    def update_processing_label():
        try:
            count = global_variables.get_kill_processing_count()
        except Exception:
            count = 0
        if count > 0:
            try:
                processing_label.config(text=f"Processing: {count}")
            except Exception:
                pass
            # Pack if not already visible
            try:
                if not processing_label.winfo_ismapped():
                    processing_label.pack(side=tk.TOP, pady=(8, 0))
            except Exception:
                pass
        else:
            # Hide when zero
            try:
                if processing_label.winfo_ismapped():
                    processing_label.pack_forget()
            except Exception:
                pass

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
    def add_pu_kill_card(title: str, subtitle: Optional[str] = None, meta: Optional[str] = None, icon: Optional[ImageTk.PhotoImage] = None, accent_color: Optional[str] = None, border_color: Optional[str] = None, insert_top: bool = False, org_picture_url: Optional[str] = None, org_sid: Optional[str] = None, victim_image_url: Optional[str] = None):
        card = _add_kill_card(left_col['container'], title, subtitle, meta, icon=icon, accent_color=accent_color, border_color=border_color, insert_top=insert_top, org_picture_url=org_picture_url, victim_image_url=victim_image_url, org_sid_tooltip=org_sid)
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

    def add_ac_kill_card(title: str, subtitle: Optional[str] = None, meta: Optional[str] = None, icon: Optional[ImageTk.PhotoImage] = None, accent_color: Optional[str] = None, border_color: Optional[str] = None, insert_top: bool = False, org_picture_url: Optional[str] = None, org_sid: Optional[str] = None, victim_image_url: Optional[str] = None):
        card = _add_kill_card(right_col['container'], title, subtitle, meta, icon=icon, accent_color=accent_color, border_color=border_color, insert_top=insert_top, org_picture_url=org_picture_url, victim_image_url=victim_image_url, org_sid_tooltip=org_sid)
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

        def _is_ac_record(rec: Dict[str, Any]) -> bool:
            # Determine AC using both game_mode and zone/location heuristics
            mode = (rec.get('game_mode') or '').lower()
            if mode in (
                'arena_commander', 'ac', 'electronic_access', 'ea_starfighter',
                'ea_duel', 'ea_freeflight', 'ea_vanduul_swarm'
            ) or any(x in mode for x in ('arena', 'electronic access')):
                return True
            zone = (rec.get('zone') or rec.get('location') or rec.get('map') or '')
            zl = zone.lower()
            # Common AC map cues
            if any(k in zl for k in ('dying star', 'broken moon', 'electronic access', 'arena')):
                return True
            return False

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
                if _is_ac_record(it):
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
                    org_sid = rec.get('org_sid')
                    org_pic = rec.get('org_picture')
                    victim_img = rec.get('victim_image')
                    # Append in sorted (descending) order to keep newest at top
                    add_fn(title, None, None, icon, accent, border, False, org_pic, org_sid, victim_img)
                except Exception:
                    continue

        _render_list(pu_items_sorted, widgets.get('add_pu_kill_card'))
        _render_list(ac_items_sorted, widgets.get('add_ac_kill_card'))

    widgets.update({
        'key_section': key_section,
        'key_entry': key_entry,
        'org_key_entry': org_key_entry,
        'org_error_label': org_error_label,
        'button_row': button_row,
        'activate_button': activate_button,
    'key_help_label': key_help_label,
        'pu_kills_frame': left_col['container'],
        'ac_kills_frame': right_col['container'],
        'pu_kills_outer': left_col['outer'],
        'ac_kills_outer': right_col['outer'],
    'details_container': middle_col,
    'details_button': details_btn,
    'processing_label': processing_label,
    'update_processing_label': update_processing_label,
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
            'player_events_outer': player_events_outer,
            'refresh_player_events': refresh_player_events,
            'add_actor_stall_card': add_actor_stall_card,
            'add_fake_hit_card': add_fake_hit_card,
            'inject_test_proximity_events': inject_test_proximity_events,
    })
    return widgets
