from screeninfo import get_monitors
from tkinter import *

def change_geom():
    global male
    
    if male:
        root.geometry("200x200+0+0")
        lbl.config(text="0")
        male = False
    else:
        root.geometry("200x200+20+20")
        lbl.config(text="20")
        male = True

    root.after(2000, change_geom)

root = Tk()
male = False
lbl = Label(root, text = "starting", font=("40"))
lbl.pack()
root.after(2000, change_geom)
print(get_monitors())
root.mainloop()



# try:
#     root.state("zoomed")
# except:
#     root.attributes('-zoomed', True)