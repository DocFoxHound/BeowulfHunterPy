import tkinter as tk
from typing import Dict, Any
import graphs

# Builds the Graphs tab contents.

def build(parent: tk.Misc, app) -> Dict[str, Any]:
    refs: Dict[str, Any] = {}

    graph_container = tk.Frame(parent, bg="#1a1a1a")
    graph_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    try:
        gw = graphs.GraphWidget(graph_container)
        setattr(app, 'graph_widget', gw)
        refs['graph_widget'] = gw
    except Exception:
        tk.Label(graph_container, text="Graph unavailable", fg="#bcbcd8", bg="#1a1a1a").pack(padx=6, pady=6, anchor='nw')
    return refs
