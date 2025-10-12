import io
import tkinter as tk
from datetime import datetime, timezone
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
        try:
            parser.refresh_api_kills_cache(global_variables.get_user_id())
        except Exception:
            pass
        kills = []
        cache = getattr(parser, 'api_kills_cache', None)
        if not cache:
            return []
        for item in cache:
            try:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    ts = item[1]
                else:
                    ts = item[1] if len(item) > 0 else None
            except Exception:
                ts = None
            dt = _parse_ts(ts)
            if dt is not None:
                kills.append(dt)
        return kills
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
        self.width = width
        self.height = height
        self.bg = bg
        self.frame = tk.Frame(parent, bg=bg, width=width)
        self.frame.pack_propagate(False)
        self.frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))

        self.image_label = tk.Label(self.frame, bg=bg)
        self.image_label.pack(fill=tk.BOTH, expand=True)
        self._photo = None

        # small control area
        ctrl = tk.Frame(self.frame, bg=bg)
        ctrl.pack(side=tk.BOTTOM, fill=tk.X)
        refresh_btn = tk.Button(ctrl, text="Refresh Graph", command=self.refresh, bg="#0f0f0f", fg="#ff5555", activebackground="#330000", activeforeground="#ffffff", relief='ridge', bd=2)
        refresh_btn.pack(side=tk.RIGHT, padx=4, pady=4)

        # initial render
        self.refresh()

    def refresh(self):
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

        xs_dates, ys = _aggregate_by_day(dts)
        # convert date to ISO strings for Plotly's x axis
        x_strs = [d.isoformat() for d in xs_dates]

        try:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=x_strs, y=ys, marker_color='#ff5555'))
            fig.update_layout(title='Kills over time', plot_bgcolor=self.bg, paper_bgcolor=self.bg, font=dict(color='white'), margin=dict(l=40, r=10, t=40, b=40))

            # export to PNG bytes
            img_bytes = fig.to_image(format='png', engine='kaleido', width=self.width, height=self.height)
            pil_im = Image.open(io.BytesIO(img_bytes))
            self._photo = ImageTk.PhotoImage(pil_im)
            self.image_label.config(image=self._photo, text='')
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

