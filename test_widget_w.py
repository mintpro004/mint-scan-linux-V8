
import customtkinter as ctk
import tkinter as tk
from widgets import Card

def test():
    root = ctk.CTk()
    frame = ctk.CTkFrame(root)
    print(f"CTkFrame _w type: {type(frame._w)}")
    print(f"CTkFrame _w value: {frame._w}")
    
    card = Card(root)
    print(f"Card _w type: {type(card._w)}")
    print(f"Card _w value: {card._w}")
    
    try:
        # This simulates what tkinter does
        child = ctk.CTkFrame(card)
        print("Successfully created child of Card")
    except Exception as e:
        print(f"Failed to create child of Card: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
