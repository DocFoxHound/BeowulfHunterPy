# Centralized theme styles for reuse across the app
import tkinter as tk
from tkinter import ttk

BUTTON_STYLE = {
    "bg": "#0f0f0f",
    "fg": "#ff5555",
    "activebackground": "#330000",
    "activeforeground": "#ffffff",
    "relief": "ridge",
    "bd": 2,
    "font": ("Times New Roman", 12),
}


def apply_ttk_styles(app: tk.Misc) -> None:
    """
    Configure a dark ttk style for Notebook, Tabs, and Frames.
    Keeps tab heights consistent and removes extra borders.
    """
    try:
        style = ttk.Style(app)
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # Base notebook styling
        style.configure('Dark.TNotebook',
                        background='#1a1a1a',
                        borderwidth=0,
                        relief='flat',
                        padding=0,
                        lightcolor='#1a1a1a',
                        darkcolor='#1a1a1a',
                        bordercolor='#1a1a1a',
                        focusthickness=0,
                        focuscolor='#1a1a1a')
        # Remove the white border/outline around the content area by simplifying layout
        try:
            # Create a plain client element to avoid themed borders
            style.element_create('Plain.Notebook.client', 'from', 'default')
            style.layout('Dark.TNotebook', [('Plain.Notebook.client', {'sticky': 'nswe'})])
        except Exception:
            try:
                style.layout('Dark.TNotebook', [('Notebook.client', {'sticky': 'nswe'})])
            except Exception:
                pass
        # Symmetric margins around the tab strip to avoid vertical offset illusion
        try:
            style.configure('Dark.TNotebook', tabmargins=[2, 2, 2, 2])
        except Exception:
            pass

        # Tab appearance (no focus ring in layout)
        try:
            style.layout('Dark.TNotebook.Tab', [
                ('Notebook.tab', {
                    'sticky': 'nswe',
                    'children': [
                        ('Notebook.padding', {
                            'side': 'top', 'sticky': 'nswe', 'children': [
                                ('Notebook.label', {'side': 'top', 'sticky': ''})
                            ]
                        })
                    ]
                })
            ])
        except Exception:
            pass
        style.configure('Dark.TNotebook.Tab',
                        background='#2a2a2a',
                        foreground='#d0d0d0',
                        padding=[10, 6],
                        font=("Times New Roman", 12),
                        focusthickness=0,
                        focuscolor='#2a2a2a',
                        relief='flat')
        # Keep tab height consistent across states by fixing padding/expand for 'selected'
        try:
            style.map('Dark.TNotebook.Tab',
                      background=[('disabled', '#1f1f1f'), ('selected', '#121212'), ('active', '#333333')],
                      foreground=[('disabled', '#7a7a7a'), ('selected', '#ff6666')],
                      padding=[('selected', [10, 6])],
                      expand=[('selected', [0, 0, 0, 0])])
        except Exception:
            # Older Tk versions may not support mapping 'expand'; ensure at least padding is consistent
            style.map('Dark.TNotebook.Tab',
                      background=[('disabled', '#1f1f1f'), ('selected', '#121212'), ('active', '#333333')],
                      foreground=[('disabled', '#7a7a7a'), ('selected', '#ff6666')],
                      padding=[('selected', [10, 6])])

        # Dark frame for notebook pages
        style.configure('Dark.TFrame', background='#1a1a1a', borderwidth=0, relief='flat')
    except Exception:
        # Styling issues should never crash the app
        pass
