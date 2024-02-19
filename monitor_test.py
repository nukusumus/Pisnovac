from screeninfo import get_monitors
from tkinter import *
import time


def switch_mon(mon):
    global root

    # root.state(NORMAL)

    s = f"{mon.width}x{mon.height}+{mon.x}+{mon.y}"
    print(s)

    root.geometry(s)
    #root.state("zoomed")

def zoom():
    global zoomed
    if zoomed:
        root.state(NORMAL)
    else:
        root.state("zoomed")
    zoomed = not zoomed

root = Tk()

mon =  get_monitors()
print(mon)
zoomed = False
Button(root, text=mon[0].name, command=lambda:switch_mon(mon[0])).pack()
Button(root, text=mon[1].name, command=lambda:switch_mon(mon[1])).pack()
Button(root, text="Zoom", command=zoom).pack()

root.mainloop()