
import customtkinter as ctk
import tkinter as tk

print(f"customtkinter version: {ctk.__version__}")

# Inspect CTkFrame
print(f"CTkFrame _w in dict: {'_w' in ctk.CTkFrame.__dict__}")
if '_w' in ctk.CTkFrame.__dict__:
    print(f"CTkFrame _w type in dict: {type(ctk.CTkFrame.__dict__['_w'])}")

# Create a mock master
class MockMaster:
    def __init__(self):
        self._w = "mock_w"
        self.tk = None

try:
    # Try to see what CTkFrame does with master._w
    # We can't easily instantiate without a display, but we can look at the MRO
    print(f"CTkFrame MRO: {ctk.CTkFrame.__mro__}")
except Exception as e:
    print(f"Error: {e}")
