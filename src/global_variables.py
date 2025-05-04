import tkinter as tk

class EventLogger:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def log(self, message):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, message + "\n")
        self.text_widget.config(state=tk.DISABLED)
        self.text_widget.see(tk.END)

# global_state.py
rsi_handle = None
logger = None
key = None
rsi_handle = None
log_file_location = None

def set_rsi_handle(handle):
    global rsi_handle
    rsi_handle = handle

def get_rsi_handle():
    return rsi_handle

def set_logger(text_area):
    global logger
    logger = EventLogger(text_area)

def get_logger():
    return logger

def set_key(text):
    global key
    key = text

def get_key():
    return key

def set_rsi_handle(handle):
    global rsi_handle
    rsi_handle = handle

def get_rsi_handle():
    return rsi_handle

def set_log_file_location(location):
    global log_file_location
    log_file_location = location

def get_log_file_location():
    return log_file_location