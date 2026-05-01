
import customtkinter as ctk
from customtkinter.windows.widgets.core_widget_classes.ctk_base_class import CTkBaseClass

print(f"CTkBaseClass _w in dict: {'_w' in CTkBaseClass.__dict__}")
if '_w' in CTkBaseClass.__dict__:
    attr = CTkBaseClass.__dict__['_w']
    print(f"CTkBaseClass _w type in dict: {type(attr)}")
    if isinstance(attr, property):
        print("It is a property!")
