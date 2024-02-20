from screeninfo import get_monitors
from tkinter import *
import time


def switch_to_secondary():

    secondary_mon = get_monitors()[0]
    for mon in get_monitors():
        if not mon.is_primary:
            secondary_mon = mon
            break
    
    s = f"{secondary_mon.width}x{secondary_mon.height}+{secondary_mon.x}+{secondary_mon.y}"
    print(s)

    root.geometry(s)
    root.update()
    root.state("zoomed")
    # root.after(50, lambda: root.state("zoomed"))

root = Tk()

Button(root, text="switch_to_secondary", command=switch_to_secondary).pack()
print(get_monitors())

root.mainloop()