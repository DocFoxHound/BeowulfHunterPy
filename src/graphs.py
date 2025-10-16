import io
import tkinter as tk
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageTk
import global_variables
import parser

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except Exception:
    PLOTLY_AVAILABLE = False

try:
    # kaleido is used by plotly to export images
    import kaleido  # noqa: F401
    KALEIDO_AVAILABLE = True
except Exception:
    KALEIDO_AVAILABLE = False


def _parse_ts(ts):
    if not ts:
        return None
    try:
        s = str(ts).strip()
        if s.startswith('<') and s.endswith('>'):
            s = s[1:-1].strip()
        s = s.strip('"').strip("'")
        if s.endswith('Z'):
            try:
                return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            except Exception:
                try:
                    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                except Exception:
                    pass
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
        try:
            secs = float(s)
            return datetime.fromtimestamp(secs, tz=timezone.utc)
        except Exception:
            return None
    except Exception:
        return None


def _gather_kill_datetimes():
    try:
        # Prefer the global_variables source ("all_kills" if present, else API-like getter)
        items = None
        try:
            items = getattr(global_variables, 'all_kills', None)
        except Exception:
            items = None

        # Fallback to accessor used by the rest of the app
        if not items:
            try:
                items = global_variables.get_api_kills_all()
            except Exception:
                items = None

        # As a last resort, try the parser cache
        parser_items = None
        if not items:
            try:
                parser.refresh_api_kills_cache(global_variables.get_user_id())
            except Exception:
                pass
            parser_items = getattr(parser, 'api_kills_cache', None)

        dts = []
        source = items if items else parser_items
        if not source:
            return []

        for item in source:
            ts = None
            try:
                # Accept a variety of shapes:
                # - dict with 'timestamp'
                # - object with .timestamp
                # - tuple/list where 2nd element is timestamp
                if isinstance(item, dict) and 'timestamp' in item:
                    ts = item.get('timestamp')
                elif hasattr(item, 'timestamp'):
                    ts = getattr(item, 'timestamp')
                elif isinstance(item, (list, tuple)):
                    if len(item) >= 2:
                        ts = item[1]
                    elif len(item) == 1:
                        ts = item[0]
                else:
                    # Some APIs return strings directly
                    if isinstance(item, str):
                        ts = item
            except Exception:
                ts = None

            dt = _parse_ts(ts)
            if dt is not None:
                dts.append(dt)
        return dts
    except Exception as e:
        global_variables.log(f"_gather_kill_datetimes failed: {e}")
        return []


def _aggregate_by_day(dts):
    counts = {}
    for dt in dts:
        try:
            day = dt.date()
            counts[day] = counts.get(day, 0) + 1
        except Exception:
            continue
    items = sorted(counts.items())
    xs = [i[0] for i in items]
    ys = [i[1] for i in items]
    return xs, ys


class GraphWidget:
    """Small widget that renders a Plotly chart to an image and embeds it in Tkinter.

    Usage: create with a parent frame (usually the right-side container in
    `log_container`). Call `.refresh()` to re-render.
    """

    def __init__(self, parent, width=420, height=480, bg="#1a1a1a"):
        self.parent = parent
        # width/height will be adapted to available space; defaults are fallbacks
        self.width = width
        self.height = height
        self.bg = bg
        self.frame = tk.Frame(parent, bg=bg)
        self.frame.pack_propagate(False)
        # Fill the whole tab area
        self.frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=(6, 6), pady=(6, 6))

        # header row with title and (yearly) period buttons
        self.header = tk.Frame(self.frame, bg=bg)
        self.header.pack(side=tk.TOP, fill=tk.X)
        self.title_label = tk.Label(self.header, text="", bg=self.bg, fg="#bcbcd8")
        self.title_label.pack(side=tk.LEFT, padx=6, pady=4)

        self.period_frame = tk.Frame(self.header, bg=bg)
        self.period_frame.pack(side=tk.RIGHT, padx=6, pady=4)
        self.range_mode = 'all'  # '1m' | '3m' | '6m' | 'all'
        self._period_buttons = {}

        def _mk_btn(lbl, mode):
            b = tk.Button(
                self.period_frame,
                text=lbl,
                command=lambda m=mode: self._set_range_mode(m),
                bg="#0f0f0f",
                fg="#bcbcd8",
                activebackground="#222",
                activeforeground="#ffffff",
                relief='ridge',
                bd=2,
                padx=6,
            )
            b.pack(side=tk.LEFT, padx=(0, 4))
            self._period_buttons[mode] = b

        _mk_btn('1m', '1m')
        _mk_btn('3m', '3m')
        _mk_btn('6m', '6m')
        _mk_btn('All', 'all')

        self.image_label = tk.Label(self.frame, bg=bg)
        self.image_label.pack(fill=tk.BOTH, expand=True)
        self._photo = None

        # small control area
        self.ctrl = tk.Frame(self.frame, bg=bg)
        self.ctrl.pack(side=tk.BOTTOM, fill=tk.X)

        # current mode label
        self.mode = 'cumulative'  # or 'yearly'
        self.mode_label = tk.Label(self.ctrl, text=self._mode_label_text(), bg=self.bg, fg="#bcbcd8")
        self.mode_label.pack(side=tk.LEFT, padx=6, pady=4)

        toggle_btn = tk.Button(
            self.ctrl,
            text="Toggle Graph",
            command=self.toggle_mode,
            bg="#0f0f0f",
            fg="#bcbcd8",
            activebackground="#222",
            activeforeground="#ffffff",
            relief='ridge',
            bd=2,
        )
        toggle_btn.pack(side=tk.RIGHT, padx=4, pady=4)

        refresh_btn = tk.Button(
            self.ctrl,
            text="Refresh Graph",
            command=self.refresh,
            bg="#0f0f0f",
            fg="#ff5555",
            activebackground="#330000",
            activeforeground="#ffffff",
            relief='ridge',
            bd=2,
        )
        refresh_btn.pack(side=tk.RIGHT, padx=4, pady=4)

        # Handle resize to keep image fitting the container
        self._resize_after_id = None
        self._last_w = None
        self._last_h = None
        self.frame.bind("<Configure>", self._on_resize)

        # initial render after layout stabilizes and we have meaningful size
        try:
            self.parent.after(50, self._schedule_first_render)
        except Exception:
            self._schedule_first_render()

    def refresh(self, force: bool = False):
        # Update target size from current layout before rendering
        try:
            self._update_size_from_layout()
        except Exception:
            pass
        # Update header visibility and button states based on mode
        try:
            self._update_header()
        except Exception:
            pass
        # Avoid rendering at extremely small size (first-pack jitter)
        if not self._has_min_size():
            try:
                # Recheck soon; this avoids showing a tiny image first
                self.frame.after(120, lambda: self.refresh(force))
                return
            except Exception:
                pass
        # Skip if size hasn't changed enough and not forced
        if not force and self._last_w is not None and self._last_h is not None:
            if abs(self.width - self._last_w) < 4 and abs(self.height - self._last_h) < 4:
                # Nothing significant changed; keep current image
                return
        if not PLOTLY_AVAILABLE:
            global_variables.log("Plotly not installed. Install plotly and kaleido to enable graphs.")
            self._show_text("Plotly not installed")
            return
        if not KALEIDO_AVAILABLE:
            global_variables.log("Kaleido not available. Install 'kaleido' to export plot images.")
            self._show_text("Kaleido not installed")
            return

        dts = _gather_kill_datetimes()
        if not dts:
            self._show_text("No kills available to plot")
            return

        try:
            if self.mode == 'cumulative':
                self._render_cumulative(dts)
            else:
                self._render_past_year(dts)
        except Exception as e:
            global_variables.log(f"Failed to render plotly image: {e}")
            self._show_text("Failed to render graph")

    def _show_text(self, text):
        # show a textual placeholder in the image area
        try:
            self.image_label.config(image='', text=text, fg='white', font=("Times New Roman", 12), compound='center')
        except Exception:
            try:
                self.image_label.config(text=text)
            except Exception:
                pass

    def get_frame(self):
        return self.frame

    # --- modes and rendering ---
    def toggle_mode(self):
        try:
            self.mode = 'yearly' if self.mode == 'cumulative' else 'cumulative'
            try:
                self.mode_label.config(text=self._mode_label_text())
            except Exception:
                pass
            try:
                self._update_header()
            except Exception:
                pass
            self.refresh(force=True)
        except Exception as e:
            global_variables.log(f"toggle_mode failed: {e}")

    def _mode_label_text(self):
        return "Mode: Cumulative" if self.mode == 'cumulative' else "Mode: Past Year"

    def _render_cumulative(self, dts):
        # Build cumulative count per day across all time
        if not dts:
            self._show_text("No kills available to plot")
            return

        # Count per day
        xs_days, day_counts = _aggregate_by_day(dts)
        if not xs_days:
            self._show_text("No kills available to plot")
            return

        # Fill missing days to make a smooth cumulative line
        start = xs_days[0]
        end = xs_days[-1]
        day_to_count = {d: c for d, c in zip(xs_days, day_counts)}
        days = []
        counts = []
        cur = start
        while cur <= end:
            days.append(cur)
            counts.append(day_to_count.get(cur, 0))
            cur = cur + timedelta(days=1)

        cumulative = []
        total = 0
        for c in counts:
            total += c
            cumulative.append(total)

        x_strs = [d.isoformat() for d in days]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_strs, y=cumulative, mode='lines+markers', line=dict(color='#ff5555')))
        fig.update_layout(
            title='',
            plot_bgcolor=self.bg,
            paper_bgcolor=self.bg,
            font=dict(color='white'),
            margin=dict(l=40, r=10, t=20, b=40),
        )

        self._render_to_image(fig)

    def _render_past_year(self, dts):
        # Non-cumulative daily kills for the past 365 days (including today)
        if not dts:
            self._show_text("No kills available to plot")
            return

        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=364)

        # Determine selected window based on header buttons
        if self.range_mode == '1m':
            sel_start = today - timedelta(days=30)
        elif self.range_mode == '3m':
            sel_start = today - timedelta(days=90)
        elif self.range_mode == '6m':
            sel_start = today - timedelta(days=180)
        else:
            sel_start = start

        # Count kills per day within selected range
        counts = {}
        for dt in dts:
            try:
                day = dt.date()
                if sel_start <= day <= today:
                    counts[day] = counts.get(day, 0) + 1
            except Exception:
                continue

        # Build complete series including zero-count days
        days = []
        ys = []
        cur = sel_start
        while cur <= today:
            days.append(cur)
            ys.append(counts.get(cur, 0))
            cur = cur + timedelta(days=1)

        if not days:
            self._show_text("No kills in the past year")
            return

        x_strs = [d.isoformat() for d in days]

        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_strs, y=ys, marker_color='#ff5555'))
        fig.update_layout(
            title='',
            plot_bgcolor=self.bg,
            paper_bgcolor=self.bg,
            font=dict(color='white'),
            margin=dict(l=40, r=10, t=20, b=40),
            xaxis=dict(
                rangeslider=dict(visible=False),
                type="date"
            )
        )

        self._render_to_image(fig)

    def _render_to_image(self, fig):
        # export to PNG bytes and show in the label
        # Guard against invalid sizes
        w = max(200, int(self.width)) if self.width else 600
        h = max(150, int(self.height)) if self.height else 320
        try:
            img_bytes = fig.to_image(format='png', engine='kaleido', width=w, height=h)
        except Exception:
            # Fallback once if engine argument causes issues
            img_bytes = fig.to_image(format='png', width=w, height=h)
        pil_im = Image.open(io.BytesIO(img_bytes))
        self._photo = ImageTk.PhotoImage(pil_im)
        self.image_label.config(image=self._photo, text='')
        # Track last rendered size
        self._last_w = w
        self._last_h = h

    # --- responsive sizing helpers ---
    def _on_resize(self, event):
        try:
            # Debounce expensive re-renders
            if self._resize_after_id is not None:
                try:
                    self.frame.after_cancel(self._resize_after_id)
                except Exception:
                    pass
            self._resize_after_id = self.frame.after(200, self.refresh)
        except Exception:
            pass

    def _update_size_from_layout(self):
        try:
            self.frame.update_idletasks()
        except Exception:
            pass
        fw = self.frame.winfo_width()
        fh = self.frame.winfo_height()
        ch = 0
        try:
            ch = self.ctrl.winfo_height()
        except Exception:
            ch = 0
        hh = 0
        try:
            hh = self.header.winfo_height()
        except Exception:
            hh = 0
        # Reserve some padding
        avail_w = max(200, fw - 12)
        avail_h = max(150, fh - ch - hh - 12)
        self.width = avail_w
        self.height = avail_h

    def _has_min_size(self):
        try:
            # Ensure the frame is mapped (visible) and we have reasonable space
            if not self.frame.winfo_ismapped():
                return False
        except Exception:
            pass
        try:
            return (self.width is not None and self.height is not None and
                    self.width >= 300 and self.height >= 200)
        except Exception:
            return False

    def _schedule_first_render(self, attempts: int = 0):
        # Wait until the widget has a decent size to avoid tiny first image
        try:
            self._update_size_from_layout()
        except Exception:
            pass
        if self._has_min_size() or attempts > 20:
            # Either we have a good size, or we've tried for ~1s; render now
            self.refresh(force=True)
            return
        try:
            self.frame.after(50, lambda: self._schedule_first_render(attempts + 1))
        except Exception:
            # As a last resort, render
            self.refresh(force=True)

    def _set_range_mode(self, mode: str):
        try:
            self.range_mode = mode
            self._update_header()
            self.refresh(force=True)
        except Exception as e:
            global_variables.log(f"_set_range_mode failed: {e}")

    def _update_header(self):
        # Title and visibility of period buttons depend on mode
        try:
            if self.mode == 'cumulative':
                self.title_label.config(text='Cumulative kills over time')
                # Hide period buttons
                try:
                    self.period_frame.pack_forget()
                except Exception:
                    pass
            else:
                self.title_label.config(text='Daily Kills (past year)')
                # Show period buttons on the right
                if not self.period_frame.winfo_ismapped():
                    self.period_frame.pack(side=tk.RIGHT, padx=6, pady=4)

            # Update button relief to indicate selection and enable state
            for m, b in self._period_buttons.items():
                try:
                    b.config(relief=('sunken' if (self.mode == 'yearly' and m == self.range_mode) else 'ridge'))
                    b.config(state=(tk.NORMAL if self.mode == 'yearly' else tk.DISABLED))
                except Exception:
                    pass
        except Exception:
            pass

