import os, sys
from tkinter import *
from tkinter import ttk
from urllib.request import urlopen
from zipfile import ZipFile
import re
from PIL import ImageTk, Image
from threading import Thread

song_url = "https://www.stud.fit.vutbr.cz/~xsterb16/Downloads/files/songs.zip"
img_url = "https://www.stud.fit.vutbr.cz/~xsterb16/Downloads/files/img.zip"
update_url = "https://www.stud.fit.vutbr.cz/~xsterb16/Downloads/files/pisnovac_android.txt"

RATIO = 1.6
FONT = "arial 8 bold"

selected_song = None
search_lock=False
img = None # aktualne zobrazeny img
photo = None
if os.path.exists("/storage/emulated/0/"):
	home_dir = "/storage/emulated/0/"
elif os.path.exists("C:/Users/Nukus/"):
	home_dir = "C:/Users/Nukus/"
elif os.path.exists("/home/nuk/smazat/"):
	home_dir = "/home/nuk/smazat/"

pisnovac_dir = home_dir + "Pisnovac/"
song_zip_path = pisnovac_dir + "songs.zip"
img_zip_path = pisnovac_dir + "img.zip"
temp_path = pisnovac_dir + "zip.tmp"
source_path = pisnovac_dir + "pisnovac_android.py"
song_list = []

transpozice = 0
transpozice_text = 0
open_song_name = ""

def download(url, tmp_path, dest_path):
	"""obecna funkce pro stazeni a ulozeni souboru"""
	with open(tmp_path, "wb") as f:
		response = urlopen(url)
		f.write(response.read())
	os.system(f"mv {tmp_path} {dest_path}")
		
def call_sync():
	t = Thread(target=sync)
	t.start()

def sync():
	"""stahne zipy s pisnemi .sbf a s nahledy"""
	sync_btn.config(text="Stahování ...", bg="orange", state=DISABLED)
	sync_btn.update()
	
	try:	
		download(img_url, temp_path, img_zip_path)
		download(song_url, temp_path, song_zip_path)
		sync_btn.config(text="Synchronizace OK", bg="#3f6")
	except:
		sync_btn.config(text="chyba synchronizace", bg="#f30")
	
	sync_btn.config(state=NORMAL)
	
	root.after(5000, lambda: sync_btn.config(text="Synchronizovat", bg="#cf6b22"))

	load_song_from_zip()
	update_songs_trw()
	

def open_song(name):
	"""misto select framu da preview frame s pisni a transpozicemi"""
	global selected_song, open_song_name, transpozice, transpozice_text
	
	if not songs_trw.selection():
		return
	
	now_selected = songs_trw.selection()[0]
		
	if selected_song  != now_selected:
		selected_song = now_selected
		return

	open_song_name = selected_song
	transpozice = 0
	transpozice_text = 0

	select_scene("view")
	update_view_img()

def select_scene(scene):
	"""vybere scenu - preview nebo select"""
	song_select_fr.pack_forget()
	song_preview_fr.pack_forget()
	global transpozice
	transpozice=0
	
	if scene == "view":
		song_preview_fr.pack(fill=BOTH, expand=1)
	elif scene == "sel":
		song_select_fr.pack(fill=BOTH, expand=1)

def update_view_img():
	global transpozice, open_song_name, img, photo
	jpg_name = open_song_name + f"{transpozice}.jpg"

	zfile = ZipFile(img_zip_path,'r')
	zfile.extract(jpg_name, pisnovac_dir)
	img = Image.open(pisnovac_dir + jpg_name)

	img = img.resize((preview_width, preview_height), Image.LANCZOS)

	photo = ImageTk.PhotoImage(img)
	os.remove(pisnovac_dir + jpg_name)

	view_canvas.image = photo
	view_canvas.create_image(int(preview_width/2), int(preview_height/2), image=photo)

def transpose(delta):
	"""handler transpose tlacitek, TODO"""
	global transpozice, transpozice_text
	transpozice = (transpozice + delta) % 12
	transpozice_text += delta
	transpozice_lbl.config(text = f"Transpozice: {transpozice_text}")
	update_view_img()

def update_songs_trw(match_list = None):
	global song_list
	for item in songs_trw.get_children():
		songs_trw.delete(item)

	song_name_list = [item[0] for item in song_list]

	if match_list is None:
		match_list = song_name_list

	for song_name in song_name_list:
		if song_name in match_list:
			songs_trw.insert("", END, song_name[:-4], text=song_name[:-4])

def unify(text: str) -> str:
	"""Funkce k odstraneni hacku a carek z textu, prevedeni pismen na lowercase a odstraneni carek v textu"""
	accented =   "áčďéěíňóřšťúůýž"
	unaccented = "acdeeinorstuuyz"

	text = text.lower()

	for letter_acc, letter_unacc in zip(list(accented), list(unaccented)):
			text = text.replace(letter_acc, letter_unacc)
	return text.replace(",", "").replace("\n", "").replace("\\", "")

def search_songs():
	global search_lock
	search_lock=False
	search_text = unify(search_entry.get())
	match_list = []
	for song in song_list:
		if search_text in unify(song[0]) or search_text in (song[1]):
			match_list.append(song[0])

	update_songs_trw(match_list)

def search_buffer(event=None):
	global search_lock
	if not search_lock:
		root.after(500, search_songs)
		search_lock=True

def load_song_from_zip():
	global song_list
	song_list = []
	# Pokud zip neexistuje, exit
	if os.path.exists(song_zip_path) and os.path.exists(img_zip_path):
		#otevreni a naskenovani song zipu
		archive = ZipFile(song_zip_path)	
		for filename in archive.namelist():
			song_data = archive.open(filename).read().decode()
			song_text=re.sub("\[[^]]*\]", "", song_data)
			song_list.append(tuple([filename, song_text]))


# updates
def update_source_file():
	try:
		download(update_url, source_path, source_path)
		update_btn.config(bg="#3f6")
	except:
		update_btn.config(bg="#f30")
	update_btn.after(5000, lambda:update_btn.config(bg="#cf6b22"))


if not os.path.exists(pisnovac_dir):
	os.mkdir(pisnovac_dir)


root = Tk()
root.geometry("600x1080")

root.update()

w_h = root.winfo_height()
w_w = root.winfo_width()

preview_width = w_w
preview_height = int(RATIO * preview_width)

style = ttk.Style(root)
# set ttk theme to "clam" which support the fieldbackground option
style.theme_use("clam")
style.configure("Treeview", background="#042A40", fieldbackground="#042A40", foreground="white", font=FONT)

song_select_fr = Frame(root, bg="#042A40")
song_preview_fr = Frame(root, bg="#042A40")

# naplneni sel sceny

sync_frame =  Frame(song_select_fr)
sync_frame.pack(fill=X)
sync_frame.columnconfigure((0,1), weight=1)
sync_frame.rowconfigure(0, weight=1)

sync_btn = Button(sync_frame, text = "Synchronizovat písně", command = call_sync, bg="#cf6b22", fg="white", font=FONT)
sync_btn.grid(row=0, column=0, sticky=NSEW)

update_btn = Button(sync_frame, text = "Stáhnout novou verzi", command = update_source_file, bg="#cf6b22", fg="white", font=FONT)
update_btn.grid(row=0, column=1, sticky=NSEW)

trw_fr = Frame(song_select_fr)
trw_fr.pack(fill=BOTH, expand=1)
trw_fr.columnconfigure(0, weight=1)
trw_fr.rowconfigure(0, weight=1)

songs_trw = ttk.Treeview(trw_fr, show = "tree")
ttk.Style().configure("Treeview", rowheight = 100)
songs_trw.bind("<<TreeviewSelect>>", open_song)
songs_trw.grid(row=0, column=0, sticky=NSEW)

scroll_bar = ttk.Scrollbar(trw_fr, orient="vertical", command=songs_trw.yview)
scroll_bar.grid(row=0, column=1, sticky=NSEW)

songs_trw.configure(yscrollcommand=scroll_bar.set)  

search_entry = Entry(song_select_fr, bg="white", relief=SUNKEN)
search_entry.bind("<KeyPress>", search_buffer)
search_entry.pack(fill=X)

#naplneni view sceny

view_canvas = Canvas(song_preview_fr, width=preview_width, height=preview_height)
# view_canvas.pack(side=CENTER)
view_canvas.place(relx=0.5, rely=0.5, anchor=CENTER)

Button(song_preview_fr, text="Zpět", command=lambda:select_scene("sel"), bg="#cf6b22", fg="white", font=FONT).pack(side=BOTTOM, fill=X)

tools_fr = Frame(song_preview_fr)
tools_fr.pack(fill=X, side=TOP)
tools_fr.rowconfigure(0, weight=1)
tools_fr.columnconfigure(1, weight=1)

Button(tools_fr, text="   -1   ",command=lambda: transpose(-1), bg="#cf6b22", fg="white", font=FONT).grid(row=0, column=0, sticky=NSEW)
transpozice_lbl = Label(tools_fr, text=f"Transpozice: {transpozice_text}", bg="#cf6b22", fg="white", relief=RAISED, font=FONT)
transpozice_lbl.grid(row=0, column=1, sticky=NSEW)
Button(tools_fr, text="   +1   ", command=lambda:transpose(1), bg="#cf6b22", fg="white", font=FONT).grid(row=0, column=2, sticky=NSEW)

select_scene("sel")

load_song_from_zip()
update_songs_trw()

root.mainloop()
