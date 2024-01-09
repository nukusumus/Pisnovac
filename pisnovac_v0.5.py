import urllib.request
import easygui
import zipfile
import sys
from tkinter import *
from tkinter import filedialog, messagebox, ttk, font, simpledialog, scrolledtext
import os
from unidecode import unidecode
from paramiko import SSHClient, AutoAddPolicy
import shutil
import time
from PIL import ImageTk, Image, ImageDraw, ImageFont
import datetime
import subprocess
import threading
from screeninfo import get_monitors

"""
Todo:
 - nahled pisne aby mel dlouhy text
"""

VERSION = "0.5"

### KONSTANTY ###
APP_NAME = "Písňovač"
TEMP_TEX_NAME = "temp.tex"
TEMP_PDF_NAME = "temp.pdf"
LATEX_FORMAT_FILE_NAME = "latex_format.txt"
IMG_ZIP_NAME = "images.zip"
SONG_ZIP_NAME = "songs.zip"
DEFAULT_IMG_NAME = "default.jpg"
SETTINGS_FILE_NAME = "settings.txt"
BG_SLIDESHOW_IMAGE_NAME = "background.jpg"
DEFAULT_SLIDESHOW_IMAGE_NAME = "background_default.jpg"
HELP_TEXT_FILE_NAME = "help_text.txt"
COLOR_FILE_NAME = "colors.txt"

DISPLAYED_SONG_PART_LENGTH = 20 # idk asi idealni delka

HOME_DIR = os.path.expanduser(f"~{os.sep}Documents{os.sep}Pisnovac{os.sep}")
SOURCE_DIR = HOME_DIR + f"Src{os.sep}"
ERR_LOG_PATH = SOURCE_DIR + "errors.log"
RECORDINGS_CACHE_DIR = HOME_DIR + f"Recordings{os.sep}"
LOCAL_SONG_LOCATION = HOME_DIR + f"Songs{os.sep}Local{os.sep}"
ONLINE_SONG_LOCATION = HOME_DIR + f"Songs{os.sep}Online{os.sep}"
LOCAL_TEMP_PATH = HOME_DIR + f"Temp{os.sep}"
SONGLISTS_DIR = HOME_DIR + f"Songlists{os.sep}"

# kontrola instalace
if not os.path.isdir(SOURCE_DIR) or not os.path.isfile(SOURCE_DIR + SETTINGS_FILE_NAME):
    easygui.msgbox("Nebyly nalezeny potřebné soubory:\n" + os.path.join(SOURCE_DIR, SETTINGS_FILE_NAME), "Chyba instalace")
    sys.exit(1)

# nahrani veci z nastaveni
with open(SOURCE_DIR + SETTINGS_FILE_NAME, "r", encoding="utf-8") as file:
    lines = file.readlines()
SERVER_ADDRESS = lines[0].rstrip()
USERNAME = lines[1].rstrip()
PWD = lines[2].rstrip()
SERVER_BASE_LOCATION = lines[3].rstrip()

# brikule, aby velikost fontu bylo cislo
SLS_FONT_STYLE = tuple(lines[4].rstrip().split(","))

SLS_FONT_COLOR:str = lines[5].rstrip()
SLS_SHADOW_COLOR:str = lines[6].rstrip().split(",")[0]
SLS_SHADOW_SIZE:str = lines[6].rstrip().split(",")[1]
SLS_BORDER_COLOR:str = lines[7].rstrip().split(",")[0]
SLS_BORDER_SIZE:str = lines[7].rstrip().split(",")[1]


SERVER_SONGS_LOCATION = SERVER_BASE_LOCATION + "Songs/" # umisteni nahravek a sbf souboru
SERVER_BACKUP_LOCATION = SERVER_BASE_LOCATION + "Backup/"  # tady se budou shromazdovat vsechny pisne pri kazde synchronizaci, uplna zaloha
SERVER_LATEX_LOCATION = SERVER_BASE_LOCATION + "Latex/"  # tady se posle .tex soubor a stahne se pdf
SERVER_ERROR_LOGS_PATH = SERVER_BASE_LOCATION + "Error_logs/"  # posilani statistik
SERVER_IMAGE_LOCATION = SERVER_BASE_LOCATION + "Images/"  # docasne uloziste obrazku ke stahnuti
SERVER_SOURCE_LOCATION = SERVER_BASE_LOCATION + "Source/"  # ulozeni defaultniho nastaveni, tex sablony
SERVER_SONGLIST_DIR = SERVER_BASE_LOCATION + "Seznamy/" # seznamy pisni

songlist_list : list = []
current_file_history : list = None # do listu uklada hostorii textu pisne
history_index = 0
save_enable = True
server_song_folder_list = [] # bude se v nem ukladat obsah adresare na serveru s pisnemi a nahravkami
editing_file_path = ""  # aktualne upravovany soubor
actual_song_directory = ""  # cesta k pisnim v offline/online rezimu
screen_mode = None  # aktualni rozlozeni UI
original_file_content = "" # pri otevreni pisne ulozi puvodni obsah pisne, pak se pouzije pro porovnani
file_tree_lock = False  # nesmi dojit k rychlemu klikani na pisne
search_lock = False  # zpozdeni vyhledavani v pisni
update_screen_lock = False
online = None  # jestli je aplikace otevrena s pristupem k internetu nebo bez
image = None  # globalni promenna pro obrazek nahledu, aby nebyl garbage collected
status_bar_orange = False
preview_pages_list = []
load_table_of_contents = None  # pozdeji se deklaruje, slouzi k ulozeni checkboxu
sls_complete_list = []  #
"""seznam pisni ve formatu [(Nazev, [(sloka, text), (sloka, text)])], kde sloka-text dvojice jsou uz v poradi danem v editoru pisni"""
sls_slides_canvas = None  # bude tu ulozeno Canvas pro slideshow mode
background_image = None  # obraz na pozadi prezentace
preview_image = None # obrazek nahledu
stg_preview_image  = None # obrazek nahledu v nastaveni
sls_treeview_selected = 0  # aktualne vybrany item ve Fronte
sls_presentation_window = None  # okno, ve kterem je prezentace
sls_slide_overlay = "clear"
loaded_preview_image_index = 0

text_size_list = [str(i * 2) for i in range(25,51)]
text_style_list =["Tučné", "Kurzíva", "Žádné"]
shadow_size_list = [str(i) for i in range(-20,21)]
border_size_list = [str(i) for i in range(0, 21)]
sls_target_slide_width = None
tags_logic = "and"
recording_name = None

PREFIX_LATEX = ""
PREFIX_TO_SONG_NAME = ""
SONG_NAME_TO_NOTE = ""
SONG_AUTHOR_TO_TEXT = ""
TABLE_CONTENTS = ""
END_LATEX = ""
LATEX_SONG_SPLITTER = ""

colors_list_cz = []
STG_COLOR_DICT = {}
STG_HELP_TEXT_LIST = []

### funkce z vlastnich importovanych knihoven ###

### sbf_to_tex.py

def to_tex(text: str) -> str:
    """
    text je text pisne, vraci prevedeny text do TEX
    """
    
    new_text = ""
    chord = ""
    next_word = ""
    section_text = ""
    loading_chord = False
    loading_next_word = False
    loading_section = False
        
    # uchovani predchozi hodnoty
    letter_history = []

    # nahrazeni znacek akordu latexem
    for letter in text:
        letter_history.append(letter)
        # kvuli latexu se musi nove radky duplikovat
        if letter == "\n":
            letter = "\n\n"
        # nacita se slovo, ktere se pak da do zavorky
        if loading_next_word:
            if (letter == " " or letter == "," or letter == "[") and next_word != "" or letter[0] == "\n":
                if letter[0] == "\n" and next_word == "":
                    next_word += " "
                new_text += "\\Ch{" + chord + "}{" + next_word + "}"
                chord = ""
                next_word = ""
                loading_next_word = False
                if letter != "[":
                    new_text += letter
                    continue
            else:
                next_word += letter
                continue

        # nacita se bezny text
        # nesmi byt elif, protoze nekdy se na tuto podminku pokracuje z predchozi
        if not loading_chord and not loading_section and not loading_next_word:
            if letter == "[":
                loading_chord = True
                continue
            elif letter == "{":
                loading_section = True
                continue
            else:
                # repetice + urceni orientace zavorky
                if letter == "|":
                    if len(letter_history) >= 2 and letter_history[-2] == ":":
                        letter = "]"
                    else:
                        letter = "["

                new_text += letter
        #nacita se akord
        elif loading_chord:
            if letter == "]":
                loading_chord = False
                loading_next_word = True
                continue
            else:
                chord += letter
        # nacita se sekce (refren, sloka)
        elif loading_section:
            if letter == "}":
                loading_section = False
                # pokud neni zadan nazev sloky, nedava se dvojtecka
                if section_text == "":    
                    new_text += "\\subsection*{" + section_text + "}"
                else:
                    new_text += "\\subsection*{" + section_text + ":}"
                
                section_text = ""
            else:
                section_text += letter

    return new_text

### text_tools.py

def parse_sections(text):
    """z textu bez akordu vrati seznam tuplu ve formatu: [(sloka, text),(sloka, text), ...]"""
    parsed_list = []
    loading_section_name = False
    section_name = ""
    section_text = ""

    for letter in text:
        if loading_section_name:
            if letter == '}':
                loading_section_name = False
            else:
                section_name += letter

        elif letter == '{':
            loading_section_name = True

            # pokud se uz nacetla nejaka sloka, ulozi se
            if len(section_text) > 0:
                parsed_list.append((section_name, section_text))
                section_text = ""
                section_name = ""
            continue

        else:
            if letter == "\n" and len(section_text) > 0 and section_text[-1] == "\n":
                continue
            if len(section_text) == 0 and letter == "\n":
                continue
            section_text += letter

    # na konci souboru se ulozi posledni sloka, ktera jiz neni ukoncena dalsim nazvem sloky
    if len(section_text) > 0:
        parsed_list.append((section_name, section_text))
    return parsed_list

def parse_text(content) -> tuple:
    """rozkouskuje text na prvnich nekolik radku a zbytek"""
    to_return = ["", "", "", "", ""]
    i = 0
    nuf_of_sorted_lines = len(to_return) - 1
    for letter in content:
        if i < nuf_of_sorted_lines:
            if letter == "\n":
                i+=1
                continue
            to_return[i] += letter
        else:
            to_return[i] += letter
    return tuple(to_return)

def ignore_chords(text: str) -> str:
    """vrati predany string bez textu v hranatych, odstrani mezery na zacatku radku a dvojite mezery"""
    skipping = False
    new_text = ""
    for letter, i in zip(text, range(len(text))):
        if skipping:
            if letter == ']':
                skipping = False
        elif letter == '[':
            skipping = True
        else:
            #odstrani mezery na zacatku radku a dvojite mezery
            if i > 0 and (letter == ' ' and (new_text[-1] == '\n' or new_text[-1] == ' ')):
                continue
            new_text += letter

    return new_text

def ignore_comments(text: str) -> str:
    """vrati predany string bez radku zacinajicich znakem %"""

    new_text = ""
    skipping = False
    for letter in text:
        if letter == '%':
            skipping = True
        elif not skipping:
            new_text += letter
            
    return new_text

def add_spaces(text: str) -> str:
    """prida dve mezery na konec a zacatek kazdeho radku, je to kvuli kurzive na canvasu, aby nedoslo k orezani"""
    splitted = text.split("\n")
    new_text = ""
    for line in splitted:
        new_text += " " + line + " \n"
        
    return new_text.rstrip().lstrip("\n") + " " # bez noveho radku na konci a zacatku, ale s mezerou na konci

def expand_backslash(text: str) -> str:
    return text.replace("\\", "\n")

def ignore_backslash(text: str) -> str:
    return text.replace("\\", "")

### transpozice.py

CHORD_LIST_DUR = [("C", "H#"),
                  ("C#", "Db"),
                  ("D",),
                  ("D#", "Eb"),
                  ("E", "Fb"),
                  ("F", "E#"),
                  ("F#", "Gb"),
                  ("G",),
                  ("G#", "Ab"),
                  ("A",),
                  ("B", "Hb", "A#"),
                  ("H", "Cb")]

CHORD_LIST_MOLL = [("c", "h#", "Cmi", "cmi"),
                   ("c#", "db"),
                   ("d", "Dmi", "dmi"),
                   ("d#", "eb"),
                   ("e", "Emi", "emi", "fb"),
                   ("e#", "f", "Fmi", "fmi"),
                   ("f#", "gb"),
                   ("g", "Gmi", "gmi"),
                   ("g#", "ab"),
                   ("a", "Ami", "ami"),
                   ("a#", "hb"),
                   ("h", "Hmi", "hmi")]


def transpose_chord(CHORD: str, POSUN: int):
    """vraci None v pripade chyby"""
    moll = False
    akord = None
    tonina = None

    # povoleny znak na zacatku akordu je zavorka
    if len(CHORD) > 0 and CHORD[0] == "(":
        CHORD = CHORD[1:]

    chord_list = CHORD_LIST_DUR
    while tonina is None or akord is None:
        for tonina_tuple in chord_list:
            for akord_string in tonina_tuple:
                if akord_string in CHORD[:3] and akord_string[0] in CHORD[:1]:
                    if tonina is None:
                        tonina = tonina_tuple
                        akord = akord_string
                    else:
                        if len(akord_string) > len(akord):
                            akord = akord_string
                            tonina = tonina_tuple
        if (tonina == None or akord == None) and moll:
            return None
        if tonina == None or akord == None:
            moll = True
            chord_list = CHORD_LIST_MOLL


    if moll:
        novy_zaklad = CHORD_LIST_MOLL[(CHORD_LIST_MOLL.index(tonina) + POSUN) % len(CHORD_LIST_MOLL)][0]
    else:
        novy_zaklad = CHORD_LIST_DUR[(CHORD_LIST_DUR.index(tonina) + POSUN) % len(CHORD_LIST_DUR)][0]
    novy_akord = novy_zaklad + CHORD[len(akord):]
    return novy_akord

### Konec vlastních importu ###

def load_help_text():
    global STG_HELP_TEXT_LIST
    with open(os.path.join(SOURCE_DIR,HELP_TEXT_FILE_NAME), "r", encoding="utf-8") as file:
        STG_HELP_TEXT_LIST = file.read().split("~")

def load_colors():
    global colors_list_cz, STG_COLOR_DICT

    # nacteni slovniku barev ze souboru
    with open(os.path.join(SOURCE_DIR, COLOR_FILE_NAME), "r", encoding="utf-8") as file:
        lines_list = file.readlines()
    colors_list_cz = lines_list[0].rstrip("\n").split(",")
    colors_list_en = lines_list[1].rstrip("\n").split(",")

    STG_COLOR_DICT = dict([(cz,en) for cz,en in zip(colors_list_cz, colors_list_en)])

def load_latex_template():
    """nahrani latexove sablony ze souboru do konstant"""
    global PREFIX_LATEX, PREFIX_TO_SONG_NAME, SONG_NAME_TO_NOTE, SONG_AUTHOR_TO_TEXT, TABLE_CONTENTS, END_LATEX, LATEX_SONG_SPLITTER
    with open(SOURCE_DIR + LATEX_FORMAT_FILE_NAME, encoding="utf-8") as file:
        content = file.read()
        list_of_constants = ["" for i in range(7)]
        i = 0
        for letter in content:
            if letter != "@":
                list_of_constants[i] += letter
            else:
                i += 1
                if i > 6:
                    break
        PREFIX_LATEX = list_of_constants[0]
        PREFIX_TO_SONG_NAME = list_of_constants[1]
        SONG_NAME_TO_NOTE = list_of_constants[2]
        SONG_AUTHOR_TO_TEXT = list_of_constants[3]
        TABLE_CONTENTS = list_of_constants[4]
        END_LATEX = list_of_constants[5]
        LATEX_SONG_SPLITTER = list_of_constants[6]

def have_internet() -> bool:
    """kdyz neni dostupny internet, vrati False, jinak True"""
    try:
        urllib.request.urlopen("http://google.com")
        return True
    except:
        return False

def on_closing():
    """zavola se, kdyz se klikne na krizek"""
    global editing_file_path
    if editing_file_path != "":
        if not messagebox.askokcancel("Info", "Ukončit? Změny budou uloženy."):
            return
    else:
        if not messagebox.askokcancel("Info", "Ukončit?"):
            return
    # ulozeni, synchronizace a zavreni pisne, pokud se nezdari, nezavre se okno
    if close_song() != 0:
        return

    # zavre se ERR_LOG_PATH
    sys.stderr.close()
    sys.stderr = sys.__stderr__
    with open(ERR_LOG_PATH, "r", encoding="utf-8") as file:
        content = file.readlines()
    # pokud je neco na druhem radku ERR_LOG_FILE (prvni je datum)
    if len(content) > 1:
        if online:
            server_comunication(
                action_list=["upload_single_file"],
                local_path_list=[ERR_LOG_PATH],
                server_path_list=[
                    SERVER_ERROR_LOGS_PATH
                    + os.path.expanduser("~/").replace("/", "")
                    + "_"
                    + datetime.datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
                ],
            )

            # vymaze se obsah log souboru
            with open(ERR_LOG_PATH, "w", encoding="utf-8") as file:
                file.write("")

    else:
        # pokud byl log prazdny, smaze ho, at priste neni plny pouze kvuli datumu
        with open(ERR_LOG_PATH, "w", encoding="utf-8") as file:
            file.write("")

    main_window.destroy()
    
def update_status(message):
    """napise message do labelu na spodni liste"""
    global status_bar_orange
    if not status_bar_orange:
        
        main_window.config(cursor="watch")
        main_window.update()

        # barvy spodni listy
        sync_status_lbl.config(bg="orange")
        sync_status_lbl.update()
        internet_status_label.config(bg="orange")
        internet_status_label.update()
        bottom_status_frame.config(bg="orange")
        bottom_status_frame.update()
        version_lbl.config(bg="orange")
        version_lbl.update()
        status_bar_orange = True

    # vlastni zprava
    sync_status_lbl.config(text=message)
    sync_status_lbl.update()

    # sekvence prikazu je hotova
    if message == "Připraven":
        sync_status_lbl.config(bg="grey")
        sync_status_lbl.update()
        internet_status_label.config(bg="grey")
        internet_status_label.update()
        bottom_status_frame.config(bg="grey")
        bottom_status_frame.update()
        version_lbl.config(bg="grey")
        version_lbl.update()
        status_bar_orange = False
        
        main_window.config(cursor="")
        main_window.update()

def pop_error(msg):
    messagebox.showerror("Chyba", msg)

def pop_info(msg: str):
    messagebox.showinfo("Info", msg)

def update_output_view():
    """vytvori tex soubor a castecny PDF jako nahled, obnovi nahled"""
    global online,preview_pages_list
    # kdyz neni online, nejde obnovit nahled
    if not online:
        pop_info("K obnovení náhledu je potřeba připojení k internetu")
        return

    # ulozi
    save_file()

    # vytvori TEX soubor, obsah ulozi do souboru TEMP_TEX_NAME
    with open(editing_file_path, "r", encoding="utf-8") as file:
        old_content = file.read()

    song_name, song_author, song_note, song_order, song_text = parse_text(old_content)
    new_text = to_tex(ignore_backslash(song_text))
    
      
    new_content = (
        PREFIX_LATEX
        + PREFIX_TO_SONG_NAME.replace("\\section", "\\section*") # nepotrebujeme cisla stranek
        + song_name
        + SONG_NAME_TO_NOTE
        + song_author
        + SONG_AUTHOR_TO_TEXT
        + new_text
        + END_LATEX
    )

    with open(LOCAL_TEMP_PATH + TEMP_TEX_NAME, "w", encoding="utf-8") as temp_file:
        temp_file.write(new_content)

    # odstrani stare nahledy
    for file in os.listdir(LOCAL_TEMP_PATH):
        if file[:4] == "page":
            os.remove(os.path.join(LOCAL_TEMP_PATH, file))

    # posle na server, tam se vytvori PDF a stahne se jpg, v pripade chyby vraci 1
    if server_comunication(["pdflatex"]) == 1:
        pop_error("error")
        return
    preview_pages_list = []
    for image_name in os.listdir(LOCAL_TEMP_PATH):
        # pouze prevedene stranky
        if image_name[:4] == "page":
            preview_pages_list.append(image_name)

    change_preview_img(i = 0)

def load_image(path, mode=None):
    """nahraje do output image labelu vybraneho podle parametru mode obrazek zadany v parametru path"""
    global image
    
    if mode == "blank":
        label = blank_image_label
    else:
        label = sbk_output_label
        preview_frame.config(text = f"Výstup - stránka {loaded_preview_image_index + 1} z {len(preview_pages_list)}")
        if DEFAULT_IMG_NAME in path:
            preview_frame.config(text = "Výstup")

    height = label.winfo_height()

    # sirka obrazu se prizpusobi
    width = int(height / 1.414)
    if height < 1 or width < 1:
        height = 965
        width = 682

    image = Image.open(path)
    image = image.resize((width, height), Image.LANCZOS)
    image = ImageTk.PhotoImage(image)
    label.config(image=image)
    label.update()

    update_tree_selection()

def rm_nl(s:str)->str:
    """odstrani jeden znak noveho radku z konce retezce"""
    if(len(s) == 0):
        return s
    if s[-1] == '\n':
        return s[0:-1]
    return s

def start_autosave():
    call_save_history()
    main_window.after(1000, start_autosave)

def call_save_history():
    process = threading.Thread(target=save_to_history)
    process.start()

def save_to_history():
    """ulozi obsah edit boxu do historie, pripadne pokud editing_file_path == "", tak vymaze historii"""
    global current_file_history, editing_file_path, save_enable, history_index

    if save_enable == False:
        return

    if editing_file_path == "":
        current_file_history = None
        history_index = -1
        return

    text_tuple = (song_name_box.get(),song_author_box.get(), song_note_box.get(), slide_order_box.get(), rm_nl(edit_mode_main_text_box.get("1.0", END)), edit_mode_main_text_box.index(INSERT))
    new_text = text_tuple[0] + text_tuple[1] + text_tuple[2] + text_tuple[3] + text_tuple[4]
    if current_file_history == None:
        history_index = 0
        current_file_history = [text_tuple]
    else:
        old_text = current_file_history[history_index][0] + current_file_history[history_index][1] + current_file_history[history_index][2] + current_file_history[history_index][3] + current_file_history[history_index][4]
        if old_text != new_text:
            history_index += 1
            current_file_history = current_file_history[0:history_index] # po uprave textu neni mozne opakovat vracene zmeny, zbytek seznamu se zahodi
            current_file_history.append(text_tuple)
    
    # aktualizace aktualni polohy kurzoru
    current_file_history[history_index] = (text_tuple[0], text_tuple[1], text_tuple[2], text_tuple[3], text_tuple[4], edit_mode_main_text_box.index(INSERT))

def history_undo():
    global current_file_history, save_enable, history_index
    save_enable = False
    if current_file_history == None:
        save_enable = True
        return
    
    if history_index <= 0:
        pop_info("Nelze vrátit zpět")
        save_enable = True
        return
    
    history_index -= 1

    new_text = current_file_history[history_index]

    song_author_box.delete("0", END)
    song_author_box.insert(INSERT, new_text[1])
    song_name_box.delete("0", END)
    song_name_box.insert(INSERT, new_text[0])
    song_note_box.delete("0", END)
    song_note_box.insert(INSERT, new_text[2])
    slide_order_box.delete("0", END)
    slide_order_box.insert(INSERT, new_text[3])
    edit_mode_main_text_box.delete("1.0", END)
    edit_mode_main_text_box.insert(INSERT, new_text[4].rstrip())
    edit_mode_main_text_box.mark_set(INSERT, new_text[5])

    # kvuli nejakemu automatickemu pridani newlinu obnovim obsah aktualni bunky
    text_tuple = (song_name_box.get(),song_author_box.get(), song_note_box.get(), slide_order_box.get(), rm_nl(edit_mode_main_text_box.get("1.0", END)), new_text[5])
    current_file_history[history_index] = text_tuple

    save_enable = True

def history_redo():
    global current_file_history, save_enable, history_index
    save_enable = False
    if current_file_history == None:
        save_enable = True
        return
    
    if history_index + 2 > len(current_file_history):
        pop_info("Nelze znovu provést")
        save_enable = True
        return
        
    edit_box_position = edit_mode_main_text_box.index(INSERT)

    history_index += 1

    new_text = current_file_history[history_index]

    song_author_box.delete("0", END)
    song_author_box.insert(INSERT, new_text[1])
    song_name_box.delete("0", END)
    song_name_box.insert(INSERT, new_text[0])
    song_note_box.delete("0", END)
    song_note_box.insert(INSERT, new_text[2])
    slide_order_box.delete("0", END)
    slide_order_box.insert(INSERT, new_text[3])
    edit_mode_main_text_box.delete("1.0", END)
    edit_mode_main_text_box.insert(INSERT, new_text[4])
    edit_mode_main_text_box.mark_set(INSERT, new_text[5])

    # kvuli nejakemu automatickemu pridani newlinu obnovim obsah aktualni bunky
    text_tuple = (song_name_box.get(),song_author_box.get(), song_note_box.get(), slide_order_box.get(), rm_nl(edit_mode_main_text_box.get("1.0", END)), new_text[5])
    current_file_history[history_index] = text_tuple

    save_enable = True

def save_file(event=None):
    """ulozeni obsahu edit boxu do aktualne upravovaneho souboru, NEUKLADA data na server"""
    update_status("Ukládání ...")
    if os.path.isfile(editing_file_path):
        with open(editing_file_path, "w", encoding="utf-8") as file:
            file.write(
                song_name_box.get()
                + "\n"
                + song_author_box.get()
                + "\n"
                + song_note_box.get()
                + "\n"
                + slide_order_box.get()
                + "\n"
                + edit_mode_main_text_box.get("1.0", END)
            )
    update_status("Připraven")

def delete_song(prompt=True):
    """odstrani vybranou pisen"""
    global editing_file_path
    if editing_file_path != "":
        answer = True
        if prompt:
            answer = messagebox.askyesno(title="Odstranit",message="Odstranit " + os.path.basename(editing_file_path) + "?",)
        if answer:
            os.remove(editing_file_path)
            base_name = os.path.basename(editing_file_path)[:-4]

            # odstraneni zaznamu

            for file in os.listdir(RECORDINGS_CACHE_DIR):
                if file[:len(base_name)] == base_name:
                    os.remove(os.path.join(RECORDINGS_CACHE_DIR,file))
                
            # odstraneni souboru na serveru
            if local_or_online_box.get() == "Online":
                to_remove_list = [SERVER_SONGS_LOCATION + file for file in server_song_folder_list if file[:len(base_name)] == base_name]
                server_comunication(["remove_single_file" for i in range(len(to_remove_list))], server_path_list=to_remove_list)
            
            editing_file_path = ""
        update_screen()

def rename_song():
    """prejmenuje pisen v aktualni slozce, pripadne i na serveru"""
    global editing_file_path
    new_name = simpledialog.askstring(title="Název", prompt="Nový název:")
    # kdyby nebylo nic zadano
    if new_name == "" or new_name is None:
        return
    
    
    # kdyby nebyla pripona, prida se
    if new_name[-4:] != ".sbf":
        new_name += ".sbf"
    new_base_name = new_name[:-4]
    old_base_name = os.path.basename(editing_file_path)[:-4]

    # prejmenuje pisen ve slozce
    shutil.move(editing_file_path, actual_song_directory + new_name)

    # pokud ma zaznam, tak ten se taky prejmenuje
    if actual_song_directory == ONLINE_SONG_LOCATION:
        # vytvoreni seznamu prikazu - vyberou se z server_listdiru soubory, co jsou nahravky k dane pisni nebo pisen sama a pridela se zbytek prikazu
        command_list = ["mv " + "\"" + SERVER_SONGS_LOCATION + file_name + "\" \"" + SERVER_SONGS_LOCATION + new_base_name + file_name[len(old_base_name):] + "\"" for file_name in server_song_folder_list if file_name[:len(old_base_name)] == old_base_name]
        server_comunication(["execute_command" for i in range(len(command_list))], command_list=command_list)
    else:
        for file_name in os.listdir(RECORDINGS_CACHE_DIR):
            if file_name[:len(old_base_name)] == old_base_name:
                shutil.move(os.path.join(RECORDINGS_CACHE_DIR, file_name), os.path.join(RECORDINGS_CACHE_DIR, new_base_name + file_name[len(old_base_name):]))

    editing_file_path = actual_song_directory + new_name
    update_screen()

def search_in_files():
    """najde ve slozce pisne, jejichz nazev nebo obsah obsahuje string zadany do vyhledavaciho pole, ignoruje male a velke pismena a unicode znaky"""
    global search_lock
    search_lock = False
    string = unidecode(search_box.get().lower())
    found_list = []

    # kdyz je vyhledavaci pole prazdne
    if string == "":
        found_list = None
        update_tree(None)
        return

    # projde kazdym souborem a hleda string, uklada do seznamu contains
    file_list = os.listdir(actual_song_directory)
    for file_name in file_list:
        # hleda pouze v souborech sbf:
        if file_name[-4:] == ".sbf":
            with open(actual_song_directory + file_name, "r", encoding="utf-8") as file:
                file_content = file.read().lower()
                if string in unidecode(ignore_chords(file_content)):
                    found_list.append(file_name)
    update_tree(found_list)

def search_buffer(event=None):
    """zabranuje prilis castemu volani funkce search_in_files"""
    global search_lock
    if not search_lock:
        main_window.after(1000, search_in_files)
        search_lock = True

def new_song():
    """vytvori novy soubor v aktualnim adresari"""
    global editing_file_path
    # kdyby byl otevreny nejaky soubor, zavre se a vycisti po nem obrazovka
    if editing_file_path != "":
        close_song()
        update_screen()
    song_name = simpledialog.askstring(title="Název", prompt="Název:")

    # kdyby se neotevrelo nic
    if song_name is None:
        return
    editing_file_path = actual_song_directory + song_name

    # pripadne doplneni pripony souboru
    if editing_file_path[-4:] != ".sbf":
        editing_file_path += ".sbf"
    with open(editing_file_path, "w", encoding="utf-8") as file:
        file.write(song_name + "\n\n\n")
    song_name_box.insert("0", song_name)
    update_screen()

def add_symbols(symbols, move_cursor=False):
    """pro vlozeni specialnich znaku"""
    position = edit_mode_main_text_box.index(INSERT)
    edit_mode_main_text_box.insert(position, symbols)
    edit_mode_main_text_box.focus()

    # u zavorek jeste posune kurzor mezi zavorky
    if move_cursor:
        edit_mode_main_text_box.mark_set(INSERT, edit_mode_main_text_box.index(INSERT) + "-1c")

def close_song(update = True) -> int:
    """zavre pisen a ulozi na server"""
    global editing_file_path
    # pokud neni otevrena zadna pisen, neni potreba nic zavirat
    if editing_file_path == "":
        return 0
    save_file()

    # nahraje se na server, pokud je otevrene uloziste online a pisen byla upravena
    if actual_song_directory == ONLINE_SONG_LOCATION:
        with open(editing_file_path, "r", encoding="utf-8") as file:
            if original_file_content != file.read():  # pokud byla pisen upravena
                if (
                    server_comunication(
                        ["upload_single_file"],
                        local_path_list=[editing_file_path],
                        server_path_list=[
                            SERVER_SONGS_LOCATION + os.path.basename(editing_file_path)
                        ],
                    )
                    != 0
                ):
                    return 1
    
    # pokud je prave ukladana pisen v rozdelane prezentaci, aktualizuje se prezentace
    presentation_list = [song[0] for song in sls_complete_list]
    if os.path.basename(editing_file_path)[:-4] in presentation_list:
        presentation_paths_list = [os.path.join(actual_song_directory, song + ".sbf") for song in presentation_list]
        sls_add_list_to_complete_list(presentation_paths_list, True)

    editing_file_path = ""

    # vymaze jpg nahledy
    # 5 je magic number, je to max. podporovany pocet stranek pisne
    for i in range(5):
        if os.path.exists(LOCAL_TEMP_PATH + "page" + str(i)):
            os.remove(LOCAL_TEMP_PATH + "page" + str(i))
        else:
            break

    # nekdy je zbytecne obnovovat obrazovku
    if update:
        update_screen()
    call_save_history()
    return 0

def copy_song():
    # kopiruje se na lokalni
    if local_or_online_box.get() == "Online":
        shutil.copy(editing_file_path, LOCAL_SONG_LOCATION)
    else:
        shutil.copy(editing_file_path, ONLINE_SONG_LOCATION)
        server_comunication(
            ["upload_single_file"],
            [editing_file_path],
            [SERVER_SONGS_LOCATION + os.path.basename(editing_file_path)],
        )
    update_screen()

def set_mode_handeler(new_mode):
    """prepina mody, je volan z eventu dropdown menu"""
    global screen_mode, preview_pages_list, actual_song_directory, preview_image

    if new_mode == screen_mode:
        return
    
    preview_pages_list = []
    
    # aby nezustal focus viset na starem widgetu
    main_window.focus()

    close_song()
    sbk_close_editor()
    sls_exit_mode()
    
    # zneviditelni vsechny widgety
    blank_frame.pack_forget()
    main_frame.pack_forget()
    main_settings_mode_frame.pack_forget()
    edit_and_songbook_frame.pack_forget()
    edit_frame.pack_forget()
    sbk_edit_frame.pack_forget()
    preview_frame.pack_forget()
    sls_navi_btn_frame.pack_forget()
    edit_mode_navi_btn_frame.pack_forget()
    slideshow_mode_frame.pack_forget()
    sbk_navi_buttons_frame.pack_forget()

    # vybere pouze potrebne widgety
    if new_mode == "edit":
        edit_mode_navi_btn_frame.pack(fill = X, expand = 0)
        edit_and_songbook_frame.pack(side=RIGHT, expand=1, fill=BOTH)
        edit_frame.pack(side=LEFT, fill = BOTH, expand = 1)
        preview_frame.pack(fill = BOTH, side = RIGHT)

        if not online:
            actual_song_directory = LOCAL_SONG_LOCATION
            local_or_online_box.current(0)

        main_frame.pack(expand=1, fill=BOTH)
        main_frame.update()
        update_screen()

    elif new_mode == "slideshow":
        sls_navi_btn_frame.pack(fill = X, expand=0)
        main_frame.pack(expand=1, fill=BOTH)
        slideshow_mode_frame.pack(fill=BOTH, expand=1)

        if preview_image is None:
            sls_setup_preview()

        for item in sls_bind_list_on_mode_change:
            item[2] = main_window.bind(item[0], item[1])
        
    elif new_mode == "songbook":
        if not online:
            pop_info("Tato funkce je dostupná pouze online")
            idk_var = screen_mode
            screen_mode = new_mode
            set_mode_handeler(idk_var)
            return
        edit_and_songbook_frame.pack(side=RIGHT, expand=1, fill=BOTH)
        preview_frame.pack(fill = BOTH, side = RIGHT)
        sbk_edit_frame.pack(side=LEFT, fill = BOTH, expand = 1)

        main_frame.pack(expand = 1, fill = BOTH)
        sbk_navi_buttons_frame.pack(fill = X, expand=0)
    elif new_mode == "settings":
        main_settings_mode_frame.pack(expand=1, fill=BOTH)
        stg_update_preview_canvas()
    elif new_mode == "blank":
        blank_frame.pack(fill=BOTH, expand=1)
        blank_frame.update()
        load_image(SOURCE_DIR + DEFAULT_IMG_NAME, mode="blank")
    screen_mode = new_mode
    main_window.update()

    # odstrani soubory v TEMP slozce
    for temp_file in os.listdir(LOCAL_TEMP_PATH):
        os.remove(LOCAL_TEMP_PATH + temp_file)

def transpose_song(action):
    """transpozice"""
    global editing_file_path

    if action == "half_tone_up":
        posun = 1
    else:
        posun = 11  # 11 misto -1

    # vytahne jednotlive akordy z textu pisne a transponuje pomoci externi funkce
    old_text = edit_mode_main_text_box.get("1.0", END)
    if "[" not in old_text or "]" not in old_text:
        pop_info("Žádný text k transpozici")
        return
    song_name = song_name_box.get()
    song_author = song_author_box.get()
    slide_order = slide_order_box.get()
    song_note = song_note_box.get()
    
    new_text = ""
    old_chord = ""
    new_chord = ""
    chars_before_chord = ""
    in_bracket = False
    for letter in old_text:
        if not in_bracket:
            new_text += letter
            if letter == "[":
                in_bracket = True
        elif in_bracket:
            if letter == "]":
                in_bracket = False
            # tyto znaky deli jednotlive akordy, basy, ale nemusi ukoncit akord
            if letter in [" ", "/", "|", "(" , "]", "-"]:
                new_chord = transpose_chord(old_chord, posun)
                if new_chord is None:
                    pop_error(f'akord "{old_chord}" nenalezen!')
                    new_chord = old_chord
                new_text += chars_before_chord + new_chord + letter
                old_chord = ""
                chars_before_chord = ""
                continue
            else:
                old_chord += letter

    with open(editing_file_path, "w", encoding="utf-8") as file:
        file.write(
            song_name
            + "\n"
            + song_author
            + "\n"
            + song_note
            + "\n"
            + slide_order
            + "\n"
            + new_text
        )

    update_screen()

def call_update_internet_status():
    """update_internet_status se vola jako podproces, protoze jinak blokuje plynulost UI"""
    process = threading.Thread(target=update_internet_status)
    process.start()
    main_window.after(5000, call_update_internet_status)

def update_internet_status():
    """zkontroluje pripojeni, obnovi widgety souvisejici s pripojenim, pripadne presune online nactene soubory na lokalni uloziste"""
    global online

    # obnovil se pristup k internetu
    if not online and have_internet():
        online = have_internet()
        pop_info("Připojení k internetu bylo obnoveno")

    # ztratil se pristup k internetu - zalohuji se soubory na lokalni uloziste
    if online and not have_internet():
        online = have_internet()
        if editing_file_path != "" and local_or_online_box.get() == "Online":
            answer = messagebox.askyesno(
                title="Připojení k internetu bylo přerušeno",
                message="Připojení k internetu bylo přerušeno.\nUložit utevřenou píseň na lokální úložiště? Jinak bude po zavření aplikace zahozena.\nPísně stejného názvu v lokálním úložišti budou přepsány!",
            )
            if answer:
                save_file()
                shutil.copy(editing_file_path, LOCAL_SONG_LOCATION)
        else:
            pop_info("Připojení k internetu bylo přerušeno")

        # aktualizuje vyber slozky v pruzkumniku
        if screen_mode == "edit":
            local_or_online_box.current(0)
            directory_changed()    

    # aktualizuje online status label
    internet_status_label.config(text="Online" if online else "Offline")

def update_screen():
    """Obnovi stav widgetu na obrazovce"""
    global online
    global editing_file_path
    global actual_song_directory
    global widgets_to_disable_enable
    global server_song_folder_list

    edit_mode_main_text_box.delete("1.0", END)
    song_name_box.delete(0, END)
    song_author_box.delete(0, END)
    song_note_box.delete(0, END)
    slide_order_box.delete(0, END)

    # zapne keybindy
    for bind_data in keybind_list:
        bind_data[2] = main_window.bind(bind_data[0], bind_data[1])

    # neni otevreny soubor
    if editing_file_path == "":
        song_name_lbl.config(text="Žádný soubor")

        # vypne widgety
        for widget in widgets_to_disable_enable:
            widget.config(state=DISABLED)

        # vypne keybindy
        for bind_data in keybind_list:
            # nektere bindy zustanou
            if bind_data[3] or screen_mode != "edit":
                main_window.unbind(bind_data[0], bind_data[2])
            
        # smaze obsah nahravek
        edt_recordings_box["values"] = ["",]
        edt_recordings_box.current(0)
        edt_recordings_box.config(state=DISABLED)

        load_image(SOURCE_DIR + DEFAULT_IMG_NAME)

    # je otevreny soubor
    else:
        # zapne widgety
        for widget in widgets_to_disable_enable:
            widget.config(state=NORMAL)

        song_name_lbl.config(text=os.path.basename(editing_file_path)[:-4])
        # nahraje do textovych poli obsah souboru
        with open(editing_file_path, "r", encoding="utf-8") as file:
            content = file.read()

            # odstrani prebytecny novy novy radek
            content = content.rstrip()

            # roztridi na nazev, poznamku a text
            song_name, song_author, song_note, slide_order, song_text = parse_text(content)

            # vlozi do prislusnych poli
            song_author_box.insert(INSERT, song_author)
            song_name_box.insert(INSERT, song_name)
            song_note_box.insert(INSERT, song_note)
            slide_order_box.insert(INSERT, slide_order)
            edit_mode_main_text_box.insert(INSERT, song_text)

        # aktualizace recording widgetu
        edt_update_recording_widgets()
            
    if local_or_online_box.get() == "Lokální":
        if not online:
            # presouvat do Online slozky se da jen kdyz online
            move_song_btn.config(state=DISABLED)
    
    update_tags_menu()
    search_in_files()
    update_tree_selection()
    call_save_history()

def edt_update_recording_widgets():
    """zjisti info o nahravkach, obnovi obsah recording widgetu"""
    song_basename = os.path.basename(editing_file_path)[:-4]
    song_name_len = len(song_basename)
    
    # opatri seznam nahravek
    if actual_song_directory == ONLINE_SONG_LOCATION:
        # projde listdir adresare s pisnemi na serveru
        recordings_list = [file_name[song_name_len + 1:] for file_name in server_song_folder_list if file_name[-4:] != ".sbf" and file_name[:song_name_len] == song_basename]
    else:
        recordings_list = [file_name[song_name_len + 1:] for file_name in os.listdir(RECORDINGS_CACHE_DIR) if file_name[-4:] != ".sbf" and file_name[:song_name_len] == song_basename]

    # zadna nahravka
    if len(recordings_list) == 0:
        edt_recordings_box["values"] = ["Žádný záznam",]
        edt_recordings_box.config(state=DISABLED)
        play_recording_btn.config(state=DISABLED)
        remove_record_btn.config(state=DISABLED)
        save_recording_btn.config(state=DISABLED)
    # nejaka nahravka
    else:
        edt_recordings_box["values"] = recordings_list
        edt_recordings_box["state"] = "readonly"
        edt_recordings_box.config(state=NORMAL)
        play_recording_btn.config(state=NORMAL)
        remove_record_btn.config(state=NORMAL)
        save_recording_btn.config(state=NORMAL)
        edt_recording_selected(name = recordings_list[0]) # metoda .current() nastavi pouze zobrazovany text, ale hodnota box.get() bude None

    edt_recordings_box.current(0)

def tags_logic_changed(event = None):
    global tags_logic
    tags_logic = "and" if navi_tags_logic_select_box.get() == "Všechny" else "or"
    search_in_files()

def update_tags_menu():
    """nacte poznamky vsech pisni oddelene carkami a da je do menu Poznamka"""
    global tags_menu_item_list, tags_menu_var_list

    new_tags_list = []
    for file_name in os.listdir(actual_song_directory):
        with open(os.path.join(actual_song_directory, file_name), "r", encoding="utf-8")as file:
            # u nových písní ještě nejsou zapsané metadata
            lines = file.readlines()
            if len(lines) < 4:
                return
            song_note = lines[2].rstrip()
            if song_note != "":
                new_tags_list += [item.rstrip().lstrip() for item in song_note.split(",")]

    # odstrani duplikaty
    new_tags_list = list(dict.fromkeys(new_tags_list))

    # jestli se seznam nezmenil, nemusi se menit menu
    if new_tags_list == tags_menu_item_list:
        return
    
    new_var_list = []
    
    for item in new_tags_list:
        # pokud item uz existuje, preda se mu hodnota ze stareho var seznamu
        if item in tags_menu_item_list:
            new_var_list.append(tags_menu_var_list[tags_menu_item_list.index(item)])
        else:
            new_var_list.append(IntVar())

    # seznamy se aktualizuji
    tags_menu_item_list = new_tags_list.copy()
    tags_menu_var_list = new_var_list.copy()

    # paralelni serazeni obou listu podle poznamky
    tuple_list = sorted([(itm, var) for itm, var in zip(tags_menu_item_list, tags_menu_var_list)], key= lambda tupl: tupl[0].lower())
    tags_menu_item_list = [tupl[0] for tupl in tuple_list]
    tags_menu_var_list = [tupl[1] for tupl in tuple_list]

    # vymaze a naplni menu
    navi_tags_menu.menu.delete(0, END)

    # tlacitko pro zruseni vyberu
    if len(new_tags_list) > 0:
        navi_tags_menu.menu.add_command(label = "Zrušit výběr", command = tags_menu_clear)
        navi_tags_menu.menu.add_separator()

    for i in range(len(tags_menu_item_list)):
        navi_tags_menu.menu.add_checkbutton(label = tags_menu_item_list[i], variable=tags_menu_var_list[i], command = search_in_files)

def tags_menu_clear():
    global tags_menu_var_list
    for var in tags_menu_var_list:
        var.set(value = 0)
    search_in_files()

def tree_item_selected(event):
    """funkce po vybrani pisne ze stromu"""
    global original_file_content, file_tree_lock, screen_mode

    # bezpecnost
    if status_bar_orange:
        return

    # pokud je slideshow mod, vybrani pisne se musi potvrdit tlacitkem "pridat vybrane"
    if screen_mode != "edit":
        return

    if not file_tree_lock:
        # zamkne zmenu pisne
        file_tree_lock = True

        # zjisti jmeno vybraneho souboru
        global editing_file_path
        if len(file_tree.selection()) > 1:
            file_tree_lock = False
            return
        item = file_tree.item(file_tree.selection())

        if item["values"] == "":
            file_tree_lock = False
            return
        # takto vypada item: item = {'text': '', 'image': '', 'values': [6, 'Pisen nova zni'], 'open': 0, 'tags': ''}
        file_name = item["values"][1] + ".sbf"

        # pokud se ma otevrit stejny soubor:
        if editing_file_path == actual_song_directory + file_name:
            file_tree_lock = False
            return

        # ulozi aktualne rozpracovany soubor
        if editing_file_path != "":
            close_song(update= False)
        editing_file_path = actual_song_directory + file_name

        # zazalohovat puvodni obsah
        with open(editing_file_path, "r", encoding="utf-8") as file:
            original_file_content = file.read()

        # odemkne dalsi zmenu pisne
        file_tree_lock = False
    update_screen()

def update_tree(found_list):
    """vycisti strom a nahraje bud vysledky hledani nebo obsah aktualne vybraneho adresare, zajistuje filtr tagu"""
    # vycisti data ze stareho seznamu
    for item in file_tree.get_children():
        file_tree.delete(item)

    # pokud jsou k dispozici vysledky hledani, preferuje je
    # seznam vyhledavani je platny

    song_name_list = []

    if found_list is not None:
        for file_name in found_list:
            song_name_list.append(file_name)

    # seznam vyhledavani je neplatny - nactou se nazvy z adresare
    else:
        # prida obsah nove slozky
        for file_name in os.listdir(actual_song_directory):
            song_name_list.append(file_name)

    #pokud je vybrana nejaka moznost filtrovani tagu, filtrovani se zapne
    tags_filter_applied = sum([i.get() for i in tags_menu_var_list])
    # vybere ze seznamu tagu ty, ktere jsou vybrane
    selected_tags_list = [item for item in tags_menu_item_list if tags_menu_var_list[tags_menu_item_list.index(item)].get() == 1]
    
    # nasazi pisne do file_tree, hleda priznaky
    for i, song_name in zip(range(len(song_name_list)), song_name_list):
        with open(os.path.join(actual_song_directory, song_name),"r",encoding="utf-8",) as file:
            song_note = file.readlines()[2].rstrip()
        # pokud hleda priznaky, projde vsechny vybrane priznaky a spocita, kolik jich pisen ma
        found_tags = 0
        if tags_filter_applied:
            for tag in selected_tags_list:
                if tag in song_note:
                    found_tags += 1
        if not tags_filter_applied or (found_tags == len(selected_tags_list) and tags_logic == "and") or (found_tags > 0 and tags_logic == "or") :
            file_tree.insert("", END, value=(i, song_name[:-4], song_note))
            
def update_tree_selection():
    # pokud je otevreny nejaky soubor, oznaci ho to
    global editing_file_path
    if editing_file_path != "":
        song_name = os.path.basename(editing_file_path)[:-4]
                
        for item in file_tree.get_children():
            if file_tree.item(item)["values"][1] == song_name:
                file_tree.selection_set(item)
                return

def server_comunication(action_list=[], local_path_list=[], server_path_list=[], command_list=[]) -> int:
    """funkce pro veskerou komunikaci se serverem
    - upload_single_file, remove_single_file, download_single_file, Online_to_server, pdflatex, execute_command"""
    global server_song_folder_list, PWD

    update_status("Připojování ... ")
    # pri prvnim otevreni je potreba zadat heslo
    write_password=False
    if PWD == "":
        write_password=True
        PWD = simpledialog.askstring("Přihlášení", "Heslo k přihlášení na server")
    try:
        update_status("Připojování ... vytvoření SSH klienta")
        client = SSHClient()
        update_status("Připojování ... načítání systémových klíčů")
        client.load_system_host_keys()
        update_status("Připojování ... nastavení chybějících klíčů")
        client.set_missing_host_key_policy(AutoAddPolicy())
        update_status("Připojování ... připojení k SSH")
        client.connect(
            hostname=SERVER_ADDRESS, username=USERNAME, password=PWD, timeout=5
        )
        update_status("Připojování ... otevření SFTP")
        sftp_client = client.open_sftp()

        # napise do nastaveni heslo
        if write_password:
            with open(SOURCE_DIR + SETTINGS_FILE_NAME, "r", encoding="utf-8") as file:
                settings_lines = file.readlines()
            settings_lines[2] = PWD + "\n"
            with open(SOURCE_DIR + SETTINGS_FILE_NAME, "w", encoding="utf-8") as file:
                file.writelines(settings_lines)
    except Exception as e:
        pop_error("Chyba připojení k serveru: " + str(e))
        sys.stderr.write(str(e))
        update_status("Připraven")
        try:
            client.close()
        except:
            pass
        if write_password:
            exit()
        return 1

    # obnovi se seznam souboru
    server_song_folder_list = sftp_client.listdir(SERVER_SONGS_LOCATION)

    for i in range(len(action_list)):
        action = action_list[i]
        if len(local_path_list) > i:
            local_path = local_path_list[i]
        if len(server_path_list) > i:
            server_path = server_path_list[i]
        if len(command_list) > i:
            command = command_list[i]

        if action == "execute_command":
            client.exec_command(command)

        # stahne seznamy pisni
        elif action == "download_songlists":
            for songlist in os.listdir(SONGLISTS_DIR):
                os.remove(os.path.join(SONGLISTS_DIR, songlist))

            for songlist_name in sftp_client.listdir(SERVER_SONGLIST_DIR):
                sftp_client.get(SERVER_SONGLIST_DIR + songlist_name, os.path.join(SONGLISTS_DIR, songlist_name))


        # nahraje se pouze jeden soubor na server do slozky songs
        elif action == "upload_single_file":
            try:
                update_status(f"Nahrávání: {local_path} -> {server_path}")
                sftp_client.put(
                    local_path,
                    server_path,
                    callback=lambda a, b: update_status(
                        f"Nahrávání: {a/1024:.0f} z {b/1024:.0f} kB"
                    ),
                )
                time.sleep(0.2)

                # vytvoreni zalohy pokud je to .sbf
                if os.path.basename(local_path)[-4:] == ".sbf":
                    update_status("Vytváření zálohy ...")
                    sftp_client.put(local_path,SERVER_BACKUP_LOCATION + 
                                    os.path.basename(server_path) + "_" + os.path.expanduser("~/").replace("/", "") + "_" +
                                    datetime.datetime.now().strftime("%d-%m-%Y_%H-%M-%S"))
                    time.sleep(0.2)
            except Exception as e:
                pop_error("Chyba:\n\n" + str(e))
                sys.stderr.write(str(e))
                update_status("Připraven")
                return 1
        # odstrani pouze jednu pisen ze serveru
        elif action == "remove_single_file":
            try:
                update_status("Odstraňování ...")
                sftp_client.remove(server_path)
            except Exception as e:
                pop_error("Chyba:\n\n" + str(e))
                sys.stderr.write(str(e))
                update_status("Připraven")
                return 1
        elif action == "download_single_file":
            try:
                update_status(f"Stahování: {server_path} -> {local_path}")
                sftp_client.get(
                    server_path,
                    local_path,
                    callback=lambda a, b: update_status(
                        f"Stahování: {a/1024:.0f} z {b/1024:.0f} kB"
                    ),
                )
            except Exception as e:
                pop_error("Chyba:\n\n" + str(e))
                sys.stderr.write(str(e))
                update_status("Připraven")
                return 1
        # stahne vsechny pisne ze serveru do Online slozky
        elif action == "server_to_Online":
            # vymaze obsah Online slozky
            update_status("Synchronizace ...:")
            for file_name in os.listdir(ONLINE_SONG_LOCATION):
                os.remove(ONLINE_SONG_LOCATION + file_name)
            # zkopiruje ze serveru do Online slozky
            update_status("Stahování ...")
            server_song_folder_list = sftp_client.listdir(SERVER_SONGS_LOCATION)
            client.exec_command(
                "cd " + SERVER_SONGS_LOCATION + "; rm songs.zip; zip songs *.sbf"
            )[1].channel.recv_exit_status()
            if SONG_ZIP_NAME in sftp_client.listdir(SERVER_SONGS_LOCATION):
                sftp_client.get(
                    SERVER_SONGS_LOCATION + SONG_ZIP_NAME,
                    ONLINE_SONG_LOCATION + SONG_ZIP_NAME,
                )
                with zipfile.ZipFile(
                    ONLINE_SONG_LOCATION + SONG_ZIP_NAME, "r"
                ) as zip_ref:
                    zip_ref.extractall(ONLINE_SONG_LOCATION)
                os.remove(ONLINE_SONG_LOCATION + SONG_ZIP_NAME)

        # nahraje .tex, na serveru z nej udela pdf, potom jpg a stahne jpg soubory
        elif action == "pdflatex":
            # vymaze docasne soubory
            client.exec_command("rm " + SERVER_LATEX_LOCATION + "*")

            sftp_client.put(
                LOCAL_TEMP_PATH + TEMP_TEX_NAME,
                SERVER_LATEX_LOCATION + TEMP_TEX_NAME,
                callback=lambda a, b: update_status(
                    f"Nahrávání TEX: {a/1024:.0f} z {b/1024:.0f}"
                ),
            )

            # prevod do PDF
            update_status("Převod do PDF ...")
            for i in range(2):
                stdout = client.exec_command(
                    "cd " + SERVER_LATEX_LOCATION + "; pdflatex " + TEMP_TEX_NAME,
                    timeout=5,
                )[1]
                stdout.channel.recv_exit_status()

            update_status("Převod do JPG ...")
            try:
                if not TEMP_PDF_NAME in sftp_client.listdir(SERVER_LATEX_LOCATION):
                    pop_error("Chyba převodu do PDF:\n" + str(stdout.read()))
                    update_status("Připraven")
                    return 1
                stdout = client.exec_command(
                    "python3 /homes/eva/xs/xsterb16/Songbook_editor/pdf_to_jpg.py",
                    timeout=5,
                )[1]
                stdout.channel.recv_exit_status()
            except Exception as e:
                pop_error(
                    "Převod do JPG se nezdařil:\n" + str(e) + "\n" + str(stdout.read())
                )
                sys.stderr.write(str(e))
                update_status("Připraven")
                return 1
            if "page0.jpg" not in sftp_client.listdir(SERVER_IMAGE_LOCATION):
                pop_error(
                    "Chyba Převodu, jpg nenalezen"
                    + str(sftp_client.listdir(SERVER_IMAGE_LOCATION))
                )
                update_status("Připraven")
                return 1
            # stahne jpg
            update_status("Stahování náhledu ...")
            client.exec_command("cd " + SERVER_IMAGE_LOCATION + "; zip images *")[
                2
            ].channel.recv_exit_status()
            sftp_client.get(
                SERVER_IMAGE_LOCATION + IMG_ZIP_NAME, LOCAL_TEMP_PATH + IMG_ZIP_NAME
            )
            update_status("Dekomprimace ...")
            with zipfile.ZipFile(LOCAL_TEMP_PATH + IMG_ZIP_NAME, "r") as zip_ref:
                zip_ref.extractall(LOCAL_TEMP_PATH)
        else:
            pop_error("Neočekávaný příkaz pro komunikaci se serverem")

    client.exec_command("rm " + SERVER_IMAGE_LOCATION + "*")
    server_song_folder_list = sftp_client.listdir(SERVER_SONGS_LOCATION)
    sftp_client.close()
    client.close()
    update_status("Připraven")
    search_in_files()
    return 0

def directory_changed(event=None):
    """combobox vyber adresare"""
    global online
    global actual_song_directory
    if local_or_online_box.get() == "Online":
        if not online and screen_mode == "edit":
            local_or_online_box.current(0)
            pop_info("Připojení k internetu není k dispzici")
            return
        move_song_btn.config(text="Kopírovat na lokální")
    else:
        move_song_btn.config(text="Kopírovat na server")
    # prehodi se actual song directory
    actual_song_directory = (
        LOCAL_SONG_LOCATION
        if local_or_online_box.get() == "Lokální"
        else ONLINE_SONG_LOCATION
    )

    close_song()
    update_screen()

def remove_recording():
    """Odstrani zaznam ze serveru a pokud je stazeny, odstrni ho i z lokalniho uloziste"""
    if not messagebox.askyesno("Odstrnit?", "Odstranit záznam?"):
        return

    if actual_song_directory == ONLINE_SONG_LOCATION:
        server_comunication(["remove_single_file",], server_path_list=[SERVER_SONGS_LOCATION + recording_name,])
    if recording_name in os.listdir(RECORDINGS_CACHE_DIR):
        os.remove(os.path.join(RECORDINGS_CACHE_DIR, recording_name))
    edt_update_recording_widgets()
    
def play_recording():
    """ujisti stazeni souboru funkci download_recording(). Pak se prehraje ve vychozim prehravaci pocitace"""
    download_recording()
    
    # spusti se vychozi aplikace prehravace v PC
    subprocess.run(["start", "", os.path.join(RECORDINGS_CACHE_DIR, recording_name)], shell=True)

def add_recording():
    """zkopiruje soubor vybrany ve filedialogu do RECORDING_CACHE_DIR a nahraje na server, vola update_screen()"""
    # vybrat soubor k nahrani
    recording = filedialog.askopenfilename(
        filetypes=[
            ("Zvukový soubor", ".m4a"),
            ("Zvukový soubor", ".mp3"),
            ("Zvukový soubor", ".wav"),
            ("Zvukový soubor", ".aac"),
        ],
        initialdir="",
        title="Vyberte záznam",
    )
    if recording == "" or recording is None:
        return
    rec_name = os.path.abspath(recording)

    # napsat k nemu poznamku
    rec_note = simpledialog.askstring(title="Název", prompt="Název:")
    if rec_note is None:
        return

    # zkopirouje se do cache slozky
    new_name_path = RECORDINGS_CACHE_DIR + os.path.basename(editing_file_path [:-4] + "_"+ rec_note + rec_name[-4:])
    if new_name_path in server_song_folder_list:
        pop_info("Soubor s tímto jménem existuje")
        return
    shutil.copy(rec_name, new_name_path)

    # nahraje na server mezi pisne
    if online:
        server_comunication(["upload_single_file"],[new_name_path],[SERVER_SONGS_LOCATION + os.path.basename(new_name_path)])
    edt_update_recording_widgets()

def download_recording():
    # pokud neni soubor v lokalnim ulozisti, stahne se
    if recording_name not in os.listdir(RECORDINGS_CACHE_DIR):
        if actual_song_directory == ONLINE_SONG_LOCATION:
            if server_comunication(["download_single_file", ], [RECORDINGS_CACHE_DIR + recording_name,],[SERVER_SONGS_LOCATION + recording_name]) != 0:
                pop_error("Chyba stahování")
                return
        else:
            # pokud neni slozka online a ma se prehrat zaznam, ktery neni stazeny, je neco spatne
            pop_error("Záznam nebyl nalezen")
            return

def save_recording():
    """zkopiruje nahravku na misto zvolene ve filedialog.asksaveas"""
    # ujisti stazeni
    download_recording()

    new_name = filedialog.asksaveasfilename(filetypes=[("Zvukový soubor", recording_name[-4:]),])
    if new_name == "" or new_name is None:
        return
    
    new_abs_path = os.path.abspath(new_name)
    # kontrola pripony
    if new_abs_path[-4:] != recording_name[-4:]:
        new_abs_path += recording_name[-4:]
    
    try:
        shutil.copy(os.path.join(RECORDINGS_CACHE_DIR, recording_name) , new_abs_path)
    except Exception as e:
        pop_error("Uložení se nezdařilo.\n" + str(e))
        sys.stderr.write(str(e))
        return
    pop_info("Soubor uložen.")

def edt_recording_selected(event = None, name = None):
    """nahraje do promenne recording_name cele jmeno nahravky"""
    global recording_name
    if name is None:
        rec_name = edt_recordings_box.get()
    else:
        rec_name = name
    recording_name = os.path.basename(editing_file_path)[:-4] + "_" + rec_name

    edt_recordings_box["state"] = "readonly"

def check_connection_initial():
    """pokud je PC offline, zepta se na Offline rezim, volane pouze pri startu programu"""
    global online
    global actual_song_directory
    actual_song_directory = ONLINE_SONG_LOCATION if online else LOCAL_SONG_LOCATION
    if not online:
        prompt = messagebox.askokcancel(
            title="", message="Bez přístupu k internetu. Otevřít v offline režimu?"
        )
        if not prompt:
            main_window.destroy()
            sys.exit()

#                          #
### SONGBOOK MODE FUNKCE ###
#                          #

def sbk_close_editor():
    """veci potrebne k zavreni songbok modu"""
    global preview_pages_list
    sbk_cancel_editing()
    sbk_export_pdf_btn.pack_forget()
    sbk_export_tex_btn.pack_forget()

def sbk_load_listbox_selection():
    sbk_latex_edit_box.delete("1.0", END)

    # prazdny vyber
    if len(file_tree.selection()) == 0:
        return

    # nahraje prefix souboru a obsah na prani
    if load_table_of_contents.get() == 1:
        sbk_latex_edit_box.insert(INSERT, PREFIX_LATEX.replace("\\usepackage{nopageno}", "") + TABLE_CONTENTS)
    else:
        sbk_latex_edit_box.insert(INSERT, PREFIX_LATEX)

    # projde vsechny vybrane polozky a nahraje je do sbk_edit_boxu
    for item_id in file_tree.selection():
        item = file_tree.item(item_id)
        full_path = actual_song_directory + item["values"][1] + ".sbf"
        with open(full_path, "r", encoding="utf-8") as file:
            song_name, song_author, song_note, slide_order, song_text = parse_text(
                file.read()
            )
            new_text = to_tex(ignore_backslash(song_text))

        # pokud se netvori obsah, nejsou potreba cisla stranek
        edited_part = PREFIX_TO_SONG_NAME if load_table_of_contents.get() else PREFIX_TO_SONG_NAME.replace("\\section", "\\section*")
        to_latex = (
            "\\newpage\n\n"
            + LATEX_SONG_SPLITTER
            + edited_part
            + song_name
            + SONG_NAME_TO_NOTE
            + song_author
            + SONG_AUTHOR_TO_TEXT
            + new_text
        )
        sbk_latex_edit_box.insert(INSERT, to_latex)

    sbk_latex_edit_box.insert(INSERT, END_LATEX)

def sbk_update_pdf():
    """volan pouze z tlacitka, vytvori PDF nahled"""
    global preview_pages_list
    content = sbk_latex_edit_box.get("1.0", END)
    # prazdny edit box
    if content == "\n":
        return

    # vycisti stare soubory
    for file in os.listdir(LOCAL_TEMP_PATH):
        os.remove(LOCAL_TEMP_PATH + file)

    # zapise se do TEX TEMP souboru a odesle ke zpracovani
    with open(LOCAL_TEMP_PATH + TEMP_TEX_NAME, "w", encoding="utf-8") as file:
        file.write(content)
    server_comunication(["pdflatex"])

    # vycisti stary seznam a naplni seznam prevedenych stranek
    preview_pages_list = []
    for image_name in os.listdir(LOCAL_TEMP_PATH):
        # pouze prevedene stranky
        if image_name[:4] == "page":
            preview_pages_list.append(image_name)
    sbk_export_pdf_btn.pack(side=RIGHT, padx=2)
    sbk_export_tex_btn.pack(side=RIGHT, padx=2)
    change_preview_img(i = 0)

def change_preview_img(i = None, delta = None):
    """funkce volana z eventu Scale nebo mousescroll, nahraje obrazek s cislem i, pripadne upravi loaded_preview_image_index"""
    global loaded_preview_image_index
    if preview_pages_list == []:
        return
    if i is None:
        if delta < 0:
            loaded_preview_image_index += 1
        elif delta > 0:
            loaded_preview_image_index -= 1
        if loaded_preview_image_index < 0:
            loaded_preview_image_index += 1
        elif loaded_preview_image_index > len(preview_pages_list) - 1:
            loaded_preview_image_index -= 1
    else:
        loaded_preview_image_index = i
    load_image(LOCAL_TEMP_PATH + f"page{loaded_preview_image_index}.jpg", "sbk")

def sbk_edit_tex_template():
    """otevre sablonu a umozni ji upravit a nahrat na server"""
    sbk_latex_edit_box.delete("1.0", END)
    with open(SOURCE_DIR + LATEX_FORMAT_FILE_NAME, "r", encoding="utf-8") as file:
        sbk_latex_edit_box.insert("1.0", file.read())
    sbk_load_selected_btn.config(state=DISABLED)
    sbk_create_pdf_btn.config(state=DISABLED)
    sbk_edit_template_btn.config(state=DISABLED)
    sbk_cancel_editing_btn.pack(side=LEFT)
    sbk_upload_template_btn.pack(side=LEFT)

def sbk_upload_template():
    """ulozi obsah latex_edit_boxu do LATEX_FORMAT souboru a odesle na server"""
    with open(SOURCE_DIR + LATEX_FORMAT_FILE_NAME, "w", encoding="utf-8") as file:
        file.write(sbk_latex_edit_box.get("1.0", END))

    server_comunication(
        ["upload_single_file"],
        [SOURCE_DIR + LATEX_FORMAT_FILE_NAME],
        [SERVER_SOURCE_LOCATION + LATEX_FORMAT_FILE_NAME],
    )
    load_latex_template()
    sbk_cancel_editing()

def sbk_cancel_editing():
    """zahodi obsah latex_edit_boxu"""
    sbk_latex_edit_box.delete("1.0", END)

    sbk_load_selected_btn.config(state=NORMAL)
    sbk_create_pdf_btn.config(state=NORMAL)
    sbk_edit_template_btn.config(state=NORMAL)
    sbk_cancel_editing_btn.pack_forget()
    sbk_upload_template_btn.pack_forget()

def sbk_export_pdf():
    """z temp.tex vytvori PDF a stahne ho na vybranou cestu ve filedialogu"""
    new_path = filedialog.asksaveasfilename(filetypes=[("PDF soubor", ".pdf")])

    # kontrola pripony
    if new_path[-4:] != ".pdf":
        new_path += ".pdf"

    server_comunication(
        ["download_single_file"], [new_path], [SERVER_LATEX_LOCATION + TEMP_PDF_NAME]
    )
    pop_info("Soubor " + os.path.basename(new_path) + " uložen.")

def sbk_export_tex():
    """zkopiruje temp.tex a ulozi na vybranou cestu"""
    new_path = filedialog.asksaveasfilename(filetypes=[("LATEX zdrojový soubor", ".tex")])
    # kontrola pripony
    if new_path[-4:] != ".tex":
        new_path += ".tex"
    # kopirovani

    shutil.copy(LOCAL_TEMP_PATH + TEMP_TEX_NAME, new_path)
    pop_info("Soubor " + os.path.basename(new_path) + " uložen.")

#                           #
### SLIDESHOW MODE FUNKCE ###
#                           #
def sls_setup_preview():
    """nastavi nahled prezentace"""
    global preview_image
    
    sls_preview_frame.update()

    padding_x = 10
    width = sls_preview_frame.winfo_width() - 2 * padding_x
    image_height = int(width * (108/192))

    padding_y = (sls_preview_frame.winfo_height() - image_height)/2
    sls_preview_frame.config(pady=padding_y if padding_y > 0 else 0, padx = padding_x)

    image = Image.open(os.path.join(SOURCE_DIR, BG_SLIDESHOW_IMAGE_NAME))
    
    preview_image = image.resize((width, image_height),Image.LANCZOS)
    preview_image = ImageTk.PhotoImage(preview_image)
    sls_preview_canvas.delete("all")
    sls_preview_canvas.create_image(0,0,image = preview_image, anchor = "nw")

def sls_exit_mode():
    """vse potrebne pro bezpecne ukonceni modu prezentace"""
    sls_end_slideshow()
    for item in sls_bind_list_on_mode_change:
        main_window.unbind(item[2])
    
    if len(get_sub_children()) > 0:
        sls_queue_treeview.selection_set(get_sub_children()[0])

def sls_queue_add_popup(event):
    """zobrazi popup s celym textem sloky"""
    tree = event.widget
    item = tree.identify_row(event.y)
    text = sls_get_item_full_text(item)
    if text != "":
        lbl.config(text = text)
        lbl.place(x=main_window.winfo_pointerx(), y=main_window.winfo_pointery())
    else:
        lbl.place_forget()

    main_window.after(500, lambda: sls_remove_popup(event.widget))

def sls_remove_popup(widget):
    """pokud pointer neni v danem widgetu, odstrani label"""
    x = main_window.winfo_pointerx()
    x1=widget.winfo_rootx()
    x2=widget.winfo_rootx() + widget.winfo_width()

    y = main_window.winfo_pointery()
    y1=widget.winfo_rooty()
    y2=widget.winfo_rooty() + widget.winfo_height()

    if x not in range(x1, x2) or y not in range(y1, y2):
        lbl.place_forget()

def sls_songlist_add_popup(event):
    """zobrazi popup s celym textem sloky"""
    tree = event.widget
    item = tree.identify_row(event.y)
    songlist_name = tree.item(item, "text")
    if songlist_name == "":
        lbl.place_forget()
        return
    with open(os.path.join(SONGLISTS_DIR, songlist_name), "r", encoding="utf-8") as file:
        text = file.read().strip().replace(".sbf", "")
    
    if text == "":
        text = "Seznam je prázdný."

    lbl.config(text = text)
    lbl.place(x=main_window.winfo_pointerx(), y=main_window.winfo_pointery())

    main_window.after(500, lambda: sls_remove_popup(event.widget))

def sls_update_queue_treeview():
    """aktualizuje treeview pisni k promitani, prida na konec prazdnou polozku "Konec prezentace" """
    global sls_complete_list

    # pridani posledniho prazdneho snimku
    if len(sls_complete_list) == 0:
        queue_list = sls_complete_list
    else:
        queue_list = sls_complete_list + [("Konec prezentace", [])]

    # vymazani vseho z treeviewu
    for item in sls_queue_treeview.get_children():
        sls_queue_treeview.delete(item)

    # aktualizuje treeview - projde sls_complete_list a vlozi jmeno, pod nej sloky a ke kazde sloce jeji text
    for i, song_tuple in zip(range(len(queue_list)), queue_list):
        name = song_tuple[0]
        sls_queue_treeview.insert("", i, f"name{i}", text=name)
        sls_queue_treeview.item(f"name{i}", open=True)
        for j, section_tuple in zip(range(len(song_tuple[1])), song_tuple[1]):
            stop_index = DISPLAYED_SONG_PART_LENGTH
            if "\n" in section_tuple[1] and section_tuple[1].index("\n") < DISPLAYED_SONG_PART_LENGTH:
                stop_index = section_tuple[1].index("\n")

            text_part_to_insert = section_tuple[1][:stop_index]
            sls_queue_treeview.insert(
                f"name{i}",
                j,
                f"section{i},{j}",
                text=section_tuple[0]
                + "   "
                + text_part_to_insert
                + "...",
            )
            
    sls_update_slide("")

def sls_update_songlist():
    """Prida do songlist treeview senamy a pisne v nich"""
    global songlist_list

    songlist_list = os.listdir(SONGLISTS_DIR)

    for item in sls_songlist_treeview.get_children():
        sls_songlist_treeview.delete(item)

    for i, songlist_name in zip(range(len(songlist_list)), songlist_list):
        sls_songlist_treeview.insert("", END, f"listname{i}", text=songlist_name)
        
        # muselo by se vyresit odstraneni a jine veci idk, stejne to asi neni potreba
        """with open(os.path.join(SONGLISTS_DIR, songlist_name), "r", encoding="utf-8") as file:
            songlist_content = file.readlines()
        for j, song_name in zip(range(len(songlist_content)), songlist_content):
            sls_songlist_treeview.insert(f"listname{i}", END, f"song{j}, {i}", text=song_name)
            sls_songlist_treeview.item(f"song{j}, {i}", open=False)"""

def ordered_section_list(section_list: list, order: str) -> list[tuple]:
    """- Z retezce poradi a seznamu slok sestavi serazeny seznam slok, kde se stejna sloka muze vyskytovat vicekrat
    - Pokud je poradi prazdny retezec, vrati nezmeneny seznam slok"""
    if order == "":
        return section_list

    # vytvori ze stringu seznam
    order_list = order.replace(" ", "").split(",")

    # sesklada novy seznam postupne podle seznamu order_list
    ordered_list = []
    for section_from_order in order_list:
        added = False
        for section_tuple in section_list:
            # porovna jmeno sloky v seznamu a v poradi slok
            if section_tuple[0] == section_from_order:
                ordered_list.append(section_tuple)
                added = True
                break

        if not added:
            pop_error(
                "Sloka "
                + section_from_order
                + " nenalezena ve slokách:"
                + str([section_tuple_2[0] for section_tuple_2 in section_list])
            )
            return section_list

    return ordered_list

def sls_add_list_to_complete_list(path_list, clear_list = False):
    """prida do sls_complete_list pisne, jejichz cesty jsou parametrem"""
    global sls_complete_list

    if clear_list:
        sls_complete_list = []

    for song_path in path_list:
        # polozka se prida do seznamu ve formatu: [(Nazev, [(V1, text), (V2, text), (R, text)]), ...]
        with open(song_path, "r", encoding="utf-8") as file:
            content = file.read()
        song_name, song_author, song_note, slide_order, song_text = parse_text(expand_backslash(ignore_chords(ignore_comments(content))))
        parsed_section_list = parse_sections(song_text)
        # dovolim vicekrat stejnou pisen, protoze to uzivatel muze chtit
        song_file_name = os.path.basename(song_path)[:-4]
        sls_complete_list.append((song_file_name,ordered_section_list(section_list=parsed_section_list, order=slide_order),))

    sls_update_queue_treeview()

def sls_add_selected():
    """prida do seznamu pisni k promitani pisne vybrane v navigacnim listview, zavola funkci sls_update_queue_treeview()"""

    if len(file_tree.selection()) == 0:
        return

    # otevre jednotlive vybrane soubory a nacte jejich obsah do seznamu, ze ktereho se vytvori Fronta
    song_path_list = []
    for item_id in file_tree.selection():
        item = file_tree.item(item_id)
        song_name = item["values"][1] + ".sbf"
        song_path = os.path.join(actual_song_directory, song_name)
        song_path_list.append(song_path)

    sls_add_list_to_complete_list(song_path_list)
    
    file_tree.selection_remove(file_tree.selection())
    sls_songlist_treeview.selection_remove(sls_songlist_treeview.selection())

def sls_pure_image(color, event=None):
    """nastavi Canvas na bilou, cernou barvu nebo prazdny obrazek pozadi"""
    global sls_slide_overlay

    if sls_slide_overlay == color or color == "clear":
        if sls_slides_canvas is not None and sls_presentation_window.winfo_width() == sls_target_slide_width:
            sls_slides_canvas.delete("overlay")
        sls_preview_canvas.delete("overlay")
        sls_slide_overlay = "clear"

        # barva tlacitek se da na puvodni
        for button in sls_tool_btns_list:
            button[0].config(relief = RAISED)
        return       
    
    for button in sls_tool_btns_list:
        button[0].config(relief = RAISED)
        if button[3] == color:
            button[0].config(relief = SUNKEN)

    else:
        if sls_slides_canvas is not None and sls_presentation_window.winfo_width() == sls_target_slide_width:
            sls_slides_canvas.create_rectangle(0,0,sls_presentation_window.winfo_width(),sls_presentation_window.winfo_height(),fill=color,tags=("overlay",))
        sls_preview_canvas.create_rectangle(0,0,sls_preview_canvas.winfo_width(),sls_preview_canvas.winfo_height(),fill=color,tags=("overlay",))
    sls_slide_overlay = color

def get_sub_children():
    """vrati seznam vsech itemu v sls_queue_treeview"""
    items_list = []
    for parents in sls_queue_treeview.get_children():
        items_list.append(parents)
        children = sls_queue_treeview.get_children(parents)
        items_list += [item for item in children]
    return items_list

def sls_change_slide(direction, event=None):
    """vybere dalsi nebo predchozi item v treeview, ten automaticky zavola sls_tree_item_selected"""
    global index

    # musi byt neco vybraneho a musi byt nejaky obsah ve Fronte
    items_list = get_sub_children()
    if sls_queue_treeview.selection() and sls_queue_treeview.selection()[0] in items_list:
        index = items_list.index(sls_queue_treeview.selection()[0])
    elif len(sls_queue_treeview.get_children()) > 0:
        sls_queue_treeview.selection_set(items_list[0])
        index = 0
    else:
        return

    if direction == "next" and index < len(items_list) - 1:
        index += 1
    elif direction == "prev" and index > 0:
        index -= 1
    elif direction == "end":
        index = len(items_list) - 1
    elif direction == "begin":
        index = 0
    sls_queue_treeview.selection_set(items_list[index])

    sls_pure_image("clear")

def sls_check_fullscreen(target_width_list):
    """kdyz je sirka okna stejna jako sirka nejake z obrazovek, udela fullscreen, nabinduje zmenu focusu a nastavi background image"""
    global sls_target_slide_width, background_image, sls_slides_canvas
    
    # muze se stat, ze se funkce zavola, kdyz uz okno neexistuje
    if sls_presentation_window is None:
        return
    
    size_x = sls_presentation_window.winfo_width()
    
    if size_x in target_width_list:
        sls_presentation_window.overrideredirect(1)
        sls_presentation_window.wm_attributes("-topmost", True)
        sls_presentation_window.update()
        sls_target_slide_width = size_x

        sls_slides_canvas = Canvas(sls_presentation_window, highlightthickness=0, bg = "black")
        sls_slides_canvas.pack(fill = BOTH, expand = 1)

        sls_presentation_window.bind("<FocusIn>", lambda e: main_window.focus())

        sls_update_slide("")
        main_window.focus()

    else:
        main_window.after(500, lambda: sls_check_fullscreen(target_width_list))

def sls_start_slideshow(event=None):
    """nabinduje klavesy k ovladani projekce, vytvori Canvas s obrazkem pozadi a nastavi slide na aktualne vybrany slide ve Fronte (pripadne prvni slide, pokud neni nic vybrano)"""
    global sls_bind_list, sls_presentation_window, index
    
    
    if len(sls_queue_treeview.get_children()) == 0:
        pop_info("Žádné písně k prezentaci")
        return

    sls_remove_selected_btn.config(state=DISABLED)
    sls_add_selected_btn.config(state=DISABLED)
    sls_start_slideshow_btn.config(state=DISABLED)

    sls_presentation_window = Toplevel(bg="black")
    sls_presentation_window.protocol("WM_DELETE_WINDOW", sls_end_slideshow)
    sls_presentation_window.geometry("640x360")
    sls_presentation_window.title("Prezentace")
    try:
        sls_presentation_window.iconbitmap(SOURCE_DIR + "icon.ico")
    except:
        pass

    monitor_width_list = [monitor.width for monitor in get_monitors()]
    
    main_window.after(500, lambda: sls_check_fullscreen(monitor_width_list))

    for item in sls_bind_list:
        item[2] = main_window.bind(item[0], item[1])

    # vybere prvni pisen a od te promita
    sls_queue_treeview.selection_set(get_sub_children()[0])
    index = 0    

    sls_tree_item_selected()

def sls_end_slideshow(event=None):
    """odbinduje klavesy prezentace a zrusi Canvas"""
    global sls_slides_canvas,sls_bind_list,sls_presentation_window,sls_target_slide_width

    for item in sls_bind_list:
        main_window.unbind(item[0])

    sls_remove_selected_btn.config(state=NORMAL)
    sls_add_selected_btn.config(state=NORMAL)
    sls_start_slideshow_btn.config(state=NORMAL)

    if sls_presentation_window is None:
        return

    sls_slides_canvas.destroy()
    sls_slides_canvas = None


    sls_presentation_window.destroy()
    sls_presentation_window = None

    sls_target_slide_width = None

    sls_preview_canvas.delete("overlay")

def sls_update_slide(text: str):
    """obnovi nahled a obsah na obrazovce"""
    global sls_target_slide_width

    processed_text = add_spaces(text)

    size_x = sls_preview_canvas.winfo_width()
    size_y = sls_preview_canvas.winfo_height()

    if sls_target_slide_width is None:
        sls_target_slide_width = main_window.winfo_width()

    # okno musi byt maximalizovane, aby se na nem zobrazily slidy
    if sls_slides_canvas is not None and sls_target_slide_width == sls_presentation_window.winfo_width():
        size_x = sls_presentation_window.winfo_width()
        size_y = sls_presentation_window.winfo_height()
        
        # promitani neni ve standartnim pomeru
        if size_y * 192 > size_x * 108:
            size_x = int(192/108 * size_y)
        elif size_y * 192 < size_x * 108:
            size_y = int(108/192 * size_x)
    else:
        size_x = 1920
        size_y = 1080

    # vytvoreni slidu pro prezentaci i nahled
    image = Image.open(os.path.join(SOURCE_DIR, BG_SLIDESHOW_IMAGE_NAME))
    slide_original_image = image.resize((size_x, size_y),Image.LANCZOS)
    obraz = ImageDraw.Draw(slide_original_image)
    try:
        font = ImageFont.truetype(SLS_FONT_STYLE[0], int(SLS_FONT_STYLE[1])) # Windows
    except:
        font = ImageFont.truetype(f"/usr/share/fonts/truetype/freefont/{SLS_FONT_STYLE[0]}", int(SLS_FONT_STYLE[1]), encoding="unic") # Unix
    # stin pisma, pokud je zapnuty
    if SLS_SHADOW_SIZE != 0:
        obraz.text((int(size_x/2) + int(SLS_SHADOW_SIZE),int(size_y/2) + int(SLS_SHADOW_SIZE)), processed_text, fill=SLS_SHADOW_COLOR, font=font,stroke_width=int(SLS_BORDER_SIZE), stroke_fill=SLS_SHADOW_COLOR, align=CENTER, anchor="mm")
    # vlastni text
    obraz.text((int(size_x/2),int(size_y/2)), processed_text, fill=SLS_FONT_COLOR, font=font,stroke_width=int(SLS_BORDER_SIZE), stroke_fill=SLS_BORDER_COLOR, align=CENTER, anchor="mm")

    slide_image = ImageTk.PhotoImage(slide_original_image)

    # obnoveni slidu pri prezentaci
    if sls_slides_canvas is not None and sls_target_slide_width == sls_presentation_window.winfo_width():
        sls_slides_canvas.delete("all")
        sls_slides_canvas.image = slide_image
        sls_slides_canvas.create_image(0, 0, image=slide_image, anchor="nw")

    slide_resized_image = slide_original_image.resize((sls_preview_canvas.winfo_width(), sls_preview_canvas.winfo_height()), Image.LANCZOS)
    preview_image = ImageTk.PhotoImage(slide_resized_image)

    sls_preview_canvas.delete("all")
    sls_preview_canvas.image = preview_image
    sls_preview_canvas.create_image(0, 0, image=preview_image, anchor="nw")

def sls_save_queue_to_songlist():
    """Ulozi aktualni frontu do vybraneho seznamu pisni"""
    if(not sls_songlist_treeview.selection()):
        pop_info("Není vybraný žádný seznam.")
        return

    songlist_name = sls_songlist_treeview.item(sls_songlist_treeview.selection()[0])["text"]

    prompt = messagebox.askyesno(title="Uložit",message=f"Seznam {songlist_name} bude přepsán. Pokračovat?")
    if not prompt:
        return

    queue_items = sls_queue_treeview.get_children()

    to_songlist_string = ""
    for item in queue_items:
        song_name = sls_queue_treeview.item(item)["text"]
        if song_name != "Konec prezentace":
            to_songlist_string += song_name + ".sbf\n"
            
    with open(os.path.join(SONGLISTS_DIR, songlist_name), "w", encoding="utf-8") as file:
        file.write(to_songlist_string)
    
    if online:
        server_comunication(["upload_single_file"], [os.path.join(SONGLISTS_DIR, songlist_name)], [SERVER_SONGLIST_DIR + songlist_name])

    pop_info(f"Uloženo do seznamu \"{songlist_name}\"")

def sls_add_songlist_to_queue():
    global actual_song_directory
    if not sls_songlist_treeview.selection():
        pop_info("Není vybraný žádný seznam.")
        return
        
    songlist_name = sls_songlist_treeview.item(sls_songlist_treeview.selection()[0])["text"]

    with open(os.path.join(SONGLISTS_DIR, songlist_name), "r", encoding="utf-8") as file:
        songs_list = file.readlines()
    songs_path_list = [os.path.join(actual_song_directory, song_name.rstrip()) for song_name in songs_list]

    # nacist pisne ze seznamu do queue treeview
    sls_add_list_to_complete_list(songs_path_list, True)

def sls_delete_songlist():
    global online

    if not sls_songlist_treeview.selection():
        pop_info("Není vybraný žádný seznam.")
        return

    songlist_name = sls_songlist_treeview.item(sls_songlist_treeview.selection()[0])["text"]

    delete = messagebox.askyesno(title="Odstranit",message=f"Odstranit {songlist_name}?")

    if not delete:
        return

    # odstraneni
    os.remove(os.path.join(SONGLISTS_DIR, songlist_name))
    if online:
        server_comunication(["remove_single_file"], [], [SERVER_SONGLIST_DIR + songlist_name])

    sls_update_songlist()

def sls_create_songlist():
    global songlist_list
    name = simpledialog.askstring(title="Nový seznam", prompt="Název seznamu:")
    if name == None or name == "":
        return
    
    if name in songlist_list:
        pop_info("Seznam s tímto názvem existuje.")
        return
    
    #vytvoreni souboru
    with open(os.path.join(SONGLISTS_DIR, name), "w", encoding="utf-8") as file:
        pass # pouze vytvori seznam

    if online:
        server_comunication(["upload_single_file"], [os.path.join(SONGLISTS_DIR, name)], [SERVER_SONGLIST_DIR + name])

    sls_update_songlist()

def sls_get_item_full_text(item):
    """z itemu queue treeviewu ziska plny text slidu"""
    parent = sls_queue_treeview.parent(item)

    # pokud existuje parent item, tzn je vybrana nejaka sloka
    if parent:
        # nacteni textu child_itemu a jeho rodice
        item_text = sls_queue_treeview.item(item)["text"]
        parent_text = sls_queue_treeview.item(parent)["text"]

        # nalezeni nadrazene pisne k vybrane sloce, nacteni textu sloky do promenne section_text
        for song in sls_complete_list:
            # nalezeni odpovidajici pisne, song[0] je nazev:
            if song[0] == parent_text:
                # nalezeni vybrane sloky
                for section_tuple in song[1]:
                    if (
                        section_tuple[0] == item_text[:len(str(section_tuple[0]))]
                        #and section_tuple[1][:DISPLAYED_SONG_PART_LENGTH] in item_text
                    ):
                        return section_tuple[1].strip()
    
    return ""

def sls_tree_item_selected(event=None):
    """handler vybrani itemu z queue treeview, vola obnoveni slidu"""
    # kdyz je focus na treeview, zachytava eventy a nefunguji bindy
    main_window.focus()

    if not sls_queue_treeview.selection():
        return
    
    section_text = sls_get_item_full_text(sls_queue_treeview.selection()[0])

    sls_update_slide(section_text)

def sls_remove_selected():
    """odstrani rodice vybraneho itemu v sls_treeeview z sls_complete_list a obnovi sls_queue_treeview"""
    selection = sls_queue_treeview.selection()
    if not selection:
        return

    item = sls_queue_treeview.selection()[0]
    parent = sls_queue_treeview.parent(item)

    # pokud existuje parent item, tzn je vybrana nejaka sloka
    if parent:
        # nacteni textu jeho rodice
        parent_text = sls_queue_treeview.item(parent)["text"]

    # neexistuje rodic = je vybran nazev pisne
    else:
        parent_text = sls_queue_treeview.item(item)["text"]

    # nalezeni odpovidajici pisne v sls_complete_list, song[0] je nazev:
    for song in sls_complete_list:
        if song[0] == parent_text:
            sls_complete_list.remove(song)
            break

    sls_update_queue_treeview()
    sls_songlist_treeview.selection_remove(sls_songlist_treeview.selection())

#                          #
### SETTINGS MODE FUNKCE ###
#                          #

def stg_list_of_fonts():
    if os.path.exists("/usr/share/fonts"):
        return [fontname for fontname in os.listdir("/usr/share/fonts/truetype/freefont/") if fontname[-4:] == ".ttf"]
    return ['arial.ttf', 'ariali.ttf', 'arialbd.ttf', 'arialbi.ttf', 'ariblk.ttf', 'bahnschrift.ttf', 'calibril.ttf', 'calibrili.ttf', 'calibri.ttf', 'calibrii.ttf', 'calibrib.ttf', 'calibriz.ttf', 'cambriai.ttf', 'cambriab.ttf', 'cambriaz.ttf', 'comic.ttf', 'comici.ttf', 'comicbd.ttf', 'comicz.ttf', 'consola.ttf', 'consolai.ttf', 'consolab.ttf', 'consolaz.ttf', 'constan.ttf', 'constani.ttf', 'constanb.ttf', 'constanz.ttf', 'corbell.ttf', 'corbelli.ttf', 'corbel.ttf', 'corbeli.ttf', 'corbelb.ttf', 'corbelz.ttf', 'cour.ttf', 'couri.ttf', 'courbd.ttf', 'courbi.ttf', 'ebrima.ttf', 'ebrimabd.ttf', 'framd.ttf', 'framdit.ttf', 'georgia.ttf', 'georgiai.ttf', 'georgiab.ttf', 'georgiaz.ttf', 'impact.ttf', 'lucon.ttf', 'l_10646.ttf', 'phagspa.ttf', 'phagspab.ttf', 'micross.ttf', 'pala.ttf', 'palai.ttf', 'palab.ttf', 'palabi.ttf', 'segoepr.ttf', 'segoeprb.ttf', 'segoesc.ttf', 'segoescb.ttf', 'segoeuil.ttf', 'seguili.ttf', 'segoeuisl.ttf', 'seguisli.ttf', 'segoeui.ttf', 'segoeuii.ttf', 'seguisb.ttf', 'seguisbi.ttf', 'segoeuib.ttf', 'segoeuiz.ttf', 'sylfaen.ttf', 'tahoma.ttf', 'tahomabd.ttf', 'times.ttf', 'timesi.ttf', 'timesbd.ttf', 'timesbi.ttf', 'trebuc.ttf', 'trebucit.ttf', 'trebucbd.ttf', 'trebucbi.ttf', 'verdana.ttf', 'verdanai.ttf', 'verdanab.ttf', 'verdanaz.ttf']

def stg_update_font_style(event = None):
    """aktualizuje styl a barvu fontu podle hodnot v nastaveni"""
    global SLS_FONT_COLOR, SLS_FONT_STYLE, SLS_SHADOW_COLOR, SLS_SHADOW_SIZE, SLS_BORDER_COLOR, SLS_BORDER_SIZE

    # zapise hodnoty do nastaveni
    with open(os.path.join(SOURCE_DIR,SETTINGS_FILE_NAME), "r", encoding="utf-8") as file:
        lines_list = file.readlines()
    # ctvrty radek = tuple se stylem
    lines_list[4] = f"{stg_font_combobox.get()},{stg_font_size_box.get()}\n"
    lines_list[5] = f"{STG_COLOR_DICT[stg_font_color_box.get()]}\n"
    lines_list[6] = f"{STG_COLOR_DICT[stg_shadow_color_box.get()]},{stg_shadow_size_box.get()}\n"
    lines_list[7] = f"{STG_COLOR_DICT[stg_border_color_box.get()]},{stg_border_size_box.get()}\n"

    with open(os.path.join(SOURCE_DIR,SETTINGS_FILE_NAME), "w", encoding="utf-8") as file:
        file.writelines(lines_list)

    # ulozi do promennych
    SLS_FONT_STYLE = tuple(lines_list[4].strip().split(","))
    SLS_FONT_COLOR = lines_list[5].strip()
    SLS_SHADOW_COLOR = lines_list[6].strip().split(",")[0]
    SLS_SHADOW_SIZE = lines_list[6].strip().split(",")[1]
    SLS_BORDER_COLOR = lines_list[7].rstrip().split(",")[0]
    SLS_BORDER_SIZE = lines_list[7].rstrip().split(",")[1]

    stg_update_preview_text()

def stg_change_backgound():
    image = filedialog.askopenfile(filetypes=(("JPG obrázek", ".jpg"),), title="Obrázek pozadí prezentace")
    if image == "" or image is None:
        return
    image_path = os.path.abspath(image.name)
    shutil.copy(image_path, os.path.join(SOURCE_DIR, BG_SLIDESHOW_IMAGE_NAME))

    stg_update_preview_canvas()

def stg_set_default_background():
    shutil.copy(os.path.join(SOURCE_DIR, DEFAULT_SLIDESHOW_IMAGE_NAME), os.path.join(SOURCE_DIR, BG_SLIDESHOW_IMAGE_NAME))

    stg_update_preview_canvas()

def stg_update_preview_canvas():
    """nastavi canvas a vlozi obrazek pozadi, vola stg_update_preview_text()"""
    global stg_preview_image

    stg_preview_frame.update()
    height = stg_preview_frame.winfo_height()
    width = int(height * 192/108)
    stg_preview_canvas.config(width = width)

    stg_update_preview_text()
    
def stg_update_preview_text():
    """obnovi text na stg_preview_canvas"""
    height = stg_preview_frame.winfo_height()
    width = int(height * 192/108)
    
    stg_preview_canvas.delete("all")

    text = """ Světlo do srdce proniká, temnota se ztrácí. \n Ježíš, Jeho jméno tu moc má, věčný život vrací. \n Pravda se všem lidem odkrývá, ano, tomu, \n kdo se na kříž podívá - bude žít, bude žít. """

    image = Image.open(os.path.join(SOURCE_DIR, BG_SLIDESHOW_IMAGE_NAME))
    slide_original_image = image.resize((1920, 1080),Image.LANCZOS)
    obraz = ImageDraw.Draw(slide_original_image)
    try:
        font = ImageFont.truetype(SLS_FONT_STYLE[0], int(SLS_FONT_STYLE[1]))
    except:
        font = ImageFont.truetype(f"/usr/share/fonts/truetype/freefont/{SLS_FONT_STYLE[0]}", int(SLS_FONT_STYLE[1]), encoding="unic") # Unix
    # stin pisma, pokud je zapnuty
    if SLS_SHADOW_SIZE != 0:
        obraz.text((int(1920/2) + int(SLS_SHADOW_SIZE),int(1080/2) + int(SLS_SHADOW_SIZE)), text, fill=SLS_SHADOW_COLOR, font=font,stroke_width=int(SLS_BORDER_SIZE), stroke_fill=SLS_SHADOW_COLOR, align=CENTER, anchor="mm")
    # vlastni text
    obraz.text((int(1920/2),int(1080/2)), text, fill=SLS_FONT_COLOR, font=font,stroke_width=int(SLS_BORDER_SIZE), stroke_fill=SLS_BORDER_COLOR, align=CENTER, anchor="mm")

    slide_resized_image = slide_original_image.resize((width, height), Image.LANCZOS)
    stg_preview_image = ImageTk.PhotoImage(slide_resized_image)

    stg_preview_canvas.delete("all")
    stg_preview_canvas.image = stg_preview_image
    stg_preview_canvas.create_image(0, 0, image=stg_preview_image, anchor="nw")

#                                 #
### INICIALIZACE OKEN A WIDGETU ###
#                                 #

# hlavni okno
if True:
    online = have_internet()
    main_window = Tk()
    main_window.title(APP_NAME)
    main_window.minsize(800, 500)
    main_window.bind("<Control-Key-1>", func=lambda e: set_mode_handeler("edit"))
    main_window.bind("<Control-Key-2>", func=lambda e: set_mode_handeler("slideshow"))
    main_window.bind("<Control-Key-3>", func=lambda e: set_mode_handeler("songbook"))
    main_window.bind("<Control-Key-4>", func=lambda e: set_mode_handeler("settings"))

    # pri pokusu o zavreni okna se zavola funkce on_closing
    main_window.protocol("WM_DELETE_WINDOW", on_closing)

    font.nametofont("TkDefaultFont").configure(size=10)

    ### dropdown menu ###
    menu = Menu(main_window)
    mode_menu = Menu(menu, tearoff=0)
    mode_menu.add_command(label="Editor textů", command=lambda: set_mode_handeler("edit"))
    mode_menu.add_command(label="Prezentace", command=lambda: set_mode_handeler("slideshow"))
    mode_menu.add_command(label="Zpěvník", command=lambda: set_mode_handeler("songbook"))
    mode_menu.add_command(label="Nastavení", command=lambda: set_mode_handeler("settings"))
    menu.add_cascade(label="Režim", menu=mode_menu)

    ### podle stavu pripojeni nastavi promenne ###
    check_connection_initial()

    main_frame = Frame(main_window)

    bottom_status_frame = Frame(main_window, padx=5, pady=5, bg="grey")
    bottom_status_frame.pack(side=BOTTOM, fill=X)

    internet_status_label = Label(bottom_status_frame, text="Online" if online else "Offline", padx=20, bg="grey")
    internet_status_label.pack(side=LEFT)

    sync_status_lbl = Label(bottom_status_frame, padx=20, text="", bg="grey")
    sync_status_lbl.pack(side=LEFT)

    version_lbl = Label(bottom_status_frame, padx=20, text="v" + VERSION, bg="grey")
    version_lbl.pack(side=RIGHT)
    
    blank_frame = Frame(main_window)
    blank_frame.pack(fill=BOTH, expand=1)

    blank_image_label = Label(blank_frame, image=image)
    blank_image_label.pack(fill=BOTH, expand=1)

# zatim se nastavi prazdna obrazovka, dokud se nestahnou data
load_image(SOURCE_DIR + DEFAULT_IMG_NAME, mode="blank")

# navigacni box
if True:
    navi_frame = LabelFrame(main_frame, text="Navigace", pady=5, padx=5, width=30)
    navi_frame.pack(side=LEFT, expand=0, fill=BOTH)

    navi_frame_top = Frame(navi_frame)
    navi_frame_top.pack(expand=0, fill=X, side = TOP)

    navi_dir_frame = LabelFrame(navi_frame, text="Umístění", pady=2, padx=2)
    navi_dir_frame.pack(expand=0, fill=X)

    navi_search_frame = LabelFrame(navi_frame, text="Hledat")
    navi_search_frame.pack(expand=0, fill=X)

    navi_frame_bottom = Frame(navi_frame)
    navi_frame_bottom.pack(expand=1, fill=BOTH)

    tags_menu_item_list = []
    tags_menu_var_list = []

    navi_tags_logic_select_box = ttk.Combobox(navi_search_frame)
    navi_tags_logic_select_box["values"] = ["Všechny", "Alespoň jedna"]
    navi_tags_logic_select_box["state"] = "readonly"
    navi_tags_logic_select_box.current(0)
    navi_tags_logic_select_box.pack(side = RIGHT, padx = 2, fill = X)
    navi_tags_logic_select_box.bind("<<ComboboxSelected>>", func=tags_logic_changed)

    search_box = Entry(navi_search_frame)
    search_box.pack(expand=1, fill=X, side=LEFT, padx = 2)
    search_box.bind("<KeyPress>", search_buffer)

    navi_tags_menu = Menubutton(navi_search_frame, text = "Poznámka ⏷", relief=FLAT, height = search_box.winfo_height())
    navi_tags_menu.menu = Menu(navi_tags_menu, tearoff=0)
    navi_tags_menu["menu"] = navi_tags_menu.menu
    navi_tags_menu.pack(side = LEFT, fill = X)

    ### Strom ###
    file_tree = ttk.Treeview(navi_frame_bottom, columns=("number", "file_name", "file_note"), show="headings")
    file_tree.heading("number", text="#")
    file_tree.column("number", minwidth=0, width=30, stretch=1)
    file_tree.heading("file_name", text="Název souboru")
    file_tree.heading("file_note", text="Poznámka")
    file_tree.bind("<<TreeviewSelect>>", tree_item_selected)
    file_tree.pack(side=LEFT, expand=1, fill=BOTH)

    ### scrollbar pro strom ###
    scrollbar = ttk.Scrollbar(navi_frame_bottom, orient=VERTICAL, command=file_tree.yview)
    file_tree.configure(yscroll=scrollbar.set)
    scrollbar.pack(side=RIGHT, fill="y")

    ### combobox pro vyber adresare ###
    local_or_online_box = ttk.Combobox(navi_dir_frame)
    local_or_online_box.pack(fill=X, expand = 0)
    local_or_online_box["values"] = ["Lokální", "Online"]
    local_or_online_box["state"] = "readonly"
    if online:
        local_or_online_box.current(1)
    else:
        local_or_online_box.current(0)
    local_or_online_box.bind("<<ComboboxSelected>>", func=directory_changed)

# spolecne pro edt a songbook
if True:
    edit_and_songbook_frame = Frame(main_frame)
    edit_and_songbook_frame.pack(side=RIGHT, expand=1, fill=BOTH)

    preview_frame = LabelFrame(edit_and_songbook_frame, text="Výstup")
    preview_frame.pack(fill = BOTH, side = RIGHT)

    sbk_output_label = Label(preview_frame, image=image)
    sbk_output_label.pack(fill=BOTH, expand=1)
    sbk_output_label.bind("<MouseWheel>", lambda e: change_preview_img(delta = e.delta))

### ### ### UI pro edit mod ### ### ###
if True:

    edit_frame = LabelFrame(edit_and_songbook_frame, text="Editor", padx=5, pady=5)
    edit_frame.pack(side = LEFT, fill = BOTH, expand = 1)

    top_edit_frame = Frame(edit_frame, pady=5)
    top_edit_frame.pack(side=TOP, fill=X)

    top_edit_frame_right = Frame(top_edit_frame)
    top_edit_frame_right.pack(side=RIGHT)

    mid_edit_frame = Frame(edit_frame, pady=10)
    mid_edit_frame.pack(fill=X)

    sub_mid_edit_frame = Frame(edit_frame)
    sub_mid_edit_frame.pack(fill=X)

    recording_frame = LabelFrame(edit_frame, text="Záznam")
    recording_frame.pack(side=BOTTOM, fill=X, expand=0)
    recording_frame.update()

    name_frame = LabelFrame(sub_mid_edit_frame, text="Název")
    name_frame.pack(side=LEFT, fill=X, expand=1)

    author_frame = LabelFrame(sub_mid_edit_frame, text="Autor")
    author_frame.pack(side=RIGHT, fill=X, expand=1)

    sub_sub_mid_edit_frame = Frame(edit_frame)
    sub_sub_mid_edit_frame.pack(fill=X)

    note_frame = LabelFrame(sub_sub_mid_edit_frame, text="Poznámka")
    note_frame.pack(side=LEFT, fill=X, expand=1)

    order_frame = LabelFrame(sub_sub_mid_edit_frame, text="Pořadí slidů")
    order_frame.pack(side=RIGHT, fill=X, expand=1)

    transpose_frame = Frame(mid_edit_frame)
    transpose_frame.grid(row=0, column=11, padx=2, sticky="nswe")
    mid_edit_frame.grid_columnconfigure(11, weight=1)

    transpose_frame_right = Frame(transpose_frame)
    transpose_frame_right.pack(side=RIGHT)

    ### tlacitka ###
    edt_update_preview_btn = Button(top_edit_frame_right,text="Obnovit náhled",command=update_output_view,width=15,state=DISABLED,)
    edt_update_preview_btn.pack(side=RIGHT, padx=2)

    close_song_btn = Button(top_edit_frame_right,text="Zavřít píseň",command=close_song,width=15,state=DISABLED)
    close_song_btn.pack(side=LEFT)

    edit_mode_navi_btn_frame = Frame(navi_frame_top)
    edit_mode_navi_btn_frame.pack(fill = X, expand=0)

    edit_mode_navi_btn_frame.rowconfigure(0, weight=1)
    edit_mode_navi_btn_frame.columnconfigure((0,1,2,3), weight = 1)

    remove_song_btn = Button(edit_mode_navi_btn_frame, text="Smazat", command=delete_song, state=DISABLED)
    remove_song_btn.grid(row = 0, column=0, sticky = "nswe")

    move_song_btn = Button(edit_mode_navi_btn_frame, text="Kopírovat na lokální" if online else "Kopírovat na server",command=copy_song,state=DISABLED,)
    move_song_btn.grid(row = 0, column=1, sticky = "nswe")

    rename_song_btn = Button(edit_mode_navi_btn_frame, text="Přejmenovat", command=rename_song, state=DISABLED)
    rename_song_btn.grid(row = 0, column=2, sticky = "nswe")

    new_song_btn = Button(edit_mode_navi_btn_frame, text="Přidat píseň", command=new_song)
    new_song_btn.grid(row = 0, column=3, sticky = "nswe")

    add_flat_btn = Button(mid_edit_frame,text="♭",command=lambda: add_symbols("b"),padx=10,state=DISABLED)
    add_flat_btn.grid(row=0, column=0)

    add_sharp_btn = Button(mid_edit_frame,text="#",command=lambda: add_symbols("#"),padx=10,state=DISABLED)
    add_sharp_btn.grid(row=0, column=1, padx=2)

    add_squirly_br_btn = Button(mid_edit_frame,text="{ }",command=lambda: add_symbols("{}", True),padx=10,state=DISABLED)
    add_squirly_br_btn.grid(row=0, column=2)

    add_sq_brackets_btn = Button(mid_edit_frame,text="[ ]",command=lambda: add_symbols("[]", True),padx=10,state=DISABLED)
    add_sq_brackets_btn.grid(row=0, column=3, padx=2)

    add_rd_brackets_btn = Button(mid_edit_frame,text="( )",command=lambda: add_symbols("()", True),padx=10,state=DISABLED)
    add_rd_brackets_btn.grid(row=0, column=5)

    add_rep_l_btn = Button(mid_edit_frame,text="|:",command=lambda: add_symbols("|:"),padx=10,state=DISABLED)
    add_rep_l_btn.grid(row=0, column=6, padx=2)

    add_rep_r_btn = Button(mid_edit_frame,text=":|",command=lambda: add_symbols(":|"),padx=10,state=DISABLED)
    add_rep_r_btn.grid(row=0, column=7)

    add_text_note_btn = Button(mid_edit_frame,text="%",command=lambda: add_symbols("%"),padx=10,state=DISABLED)
    add_text_note_btn.grid(row=0, column=8, padx=2)

    add_backslash_btn = Button(mid_edit_frame,text="\\",command=lambda: add_symbols("\\"),padx=10,state=DISABLED)
    add_backslash_btn.grid(row=0, column=9)

    traspose_up_btn = Button(transpose_frame_right,text=" Transpozice + 1",command=lambda: transpose_song("half_tone_up"),width=15,state=DISABLED)
    traspose_up_btn.pack(side=LEFT, padx=2)

    traspose_down_btn = Button(transpose_frame_right,text="Transpozice - 1",command=lambda: transpose_song("half_tone_down"),width=15,state=DISABLED)
    traspose_down_btn.pack(side=RIGHT)

    remove_record_btn = Button(recording_frame, text="Smazat", command=remove_recording, state=DISABLED)
    remove_record_btn.pack(side=RIGHT, padx=2)

    play_recording_btn = Button(recording_frame, text="Přehrát", command=play_recording, state=DISABLED)
    play_recording_btn.pack(side=RIGHT)

    save_recording_btn = Button(recording_frame, text="Uložit jako", command=save_recording, state=DISABLED)
    save_recording_btn.pack(side=RIGHT, padx = 2)

    new_recording_btn = Button(recording_frame, text="Nová nahrávka", command=add_recording, state=DISABLED)
    new_recording_btn.pack(side=RIGHT)

    edt_recordings_box = ttk.Combobox(recording_frame, width = int(main_window.winfo_width()/30))
    edt_recordings_box["values"] = []
    edt_recordings_box.pack(side = LEFT, pady = 2, padx = 2)
    edt_recordings_box.bind("<<ComboboxSelected>>", func=edt_recording_selected)

    song_name_lbl = Label(top_edit_frame, font="Tahoma 12 bold")
    song_name_lbl.pack(side=LEFT)

    edit_mode_main_text_box = Text(edit_frame)
    edit_mode_main_text_box.pack(expand=True, fill=BOTH)

    song_name_box = Entry(name_frame)
    song_name_box.pack(expand=0, fill=X)

    song_author_box = Entry(author_frame)
    song_author_box.pack(expand=0, fill=X)

    song_note_box = Entry(note_frame)
    song_note_box.pack(expand=0, fill=X)

    slide_order_box = Entry(order_frame)
    slide_order_box.pack(expand=0, fill=X)

### ### ### UI pro prezentaci ### ### ###
if True:

    slideshow_mode_frame = Frame(main_frame)

    sls_queue_and_songlist_frame = Frame(slideshow_mode_frame, padx=2, pady=2)
    sls_queue_and_songlist_frame.pack(side=LEFT, fill=Y)

    sls_queue_treeview_frame = LabelFrame(sls_queue_and_songlist_frame, text="Fronta", padx=2, pady=2, width = 300)
    sls_queue_treeview_frame.pack(side=TOP, expand=1, fill=BOTH)

    sls_songlist_frame = LabelFrame(sls_queue_and_songlist_frame, text = "Seznamy", padx = 2, pady = 2)
    sls_songlist_frame.pack(side=BOTTOM, expand=1, fill=BOTH)

    sls_tools_n_preview_frame = Frame(slideshow_mode_frame)
    sls_tools_n_preview_frame.pack(side = RIGHT, fill = BOTH, expand=1)

    sls_tools_frame = LabelFrame(sls_tools_n_preview_frame, text = "Nástroje", padx = 2, pady = 2)
    sls_tools_frame.pack(fill = X, expand=0)

    sls_tool_btns_list = [[None, lambda: sls_pure_image("black"), "Černé [B]", "black"],
                          [None, lambda: sls_pure_image("white"), "Bílé [W]", "white"],
                          [None, lambda: sls_pure_image("clear"), "Normální [C]", "clear"]]

    for button in sls_tool_btns_list:
        button[0] = Button(sls_tools_frame, text = button[2], command=button[1])
        button[0].pack(side = LEFT, padx = 2, pady = 2)

    sls_preview_frame = LabelFrame(sls_tools_n_preview_frame, text = "Náhled")
    sls_preview_frame.pack(fill = BOTH, expand=1)

    sls_preview_canvas = Canvas(sls_preview_frame, highlightthickness=1, highlightcolor="grey", highlightbackground="grey")
    sls_preview_canvas.pack(fill = BOTH, expand=1)

    sls_navi_btn_frame = Frame(navi_frame_top)
    sls_navi_btn_frame.pack(fill = X, expand = 0)

    sls_add_selected_btn = Button(sls_navi_btn_frame, text="Přidat vybrané do fronty", command=sls_add_selected)
    sls_add_selected_btn.pack(fill=X, expand=0)

    sls_screen_select_frame = LabelFrame(sls_queue_treeview_frame, text="Obrazovka")
    sls_screen_select_frame.pack(fill=X, expand=0)

    sls_start_slideshow_btn = Button(sls_queue_treeview_frame, text="Spustit prezentaci", command=sls_start_slideshow)
    sls_start_slideshow_btn.pack(fill=X, expand=0, pady=2)

    sls_remove_selected_btn = Button(sls_queue_treeview_frame, text="Odstranit vybranou píseň", command=sls_remove_selected)
    sls_remove_selected_btn.pack(fill=X, expand=0, pady=2)
    
    sls_create_songlist_btn = Button(sls_songlist_frame, text="Vytvořit nový seznam", command=sls_create_songlist)
    sls_create_songlist_btn.pack(fill=X, expand=0, pady=2)

    sls_remove_songlist_btn = Button(sls_songlist_frame, text="Odstranit vybraný seznam", command=sls_delete_songlist)
    sls_remove_songlist_btn.pack(fill=X, expand=0, pady=2)

    sls_save_to_songlist_btn = Button(sls_songlist_frame, text="Uložit frontu do vybraného seznamu", command=sls_save_queue_to_songlist)
    sls_save_to_songlist_btn.pack(fill=X, expand=0, pady=2)

    sls_add_to_queue_btn = Button(sls_songlist_frame, text="Nahrát seznam do fronty", command=sls_add_songlist_to_queue)
    sls_add_to_queue_btn.pack(fill=X, expand=0, pady=2)

    widget_default_color = sls_remove_selected_btn.cget("background")

    sls_queue_treeview = ttk.Treeview(sls_queue_treeview_frame, show="tree")
    sls_queue_treeview.pack(fill=BOTH, expand=1)
    sls_queue_treeview.bind("<<TreeviewSelect>>", sls_tree_item_selected)
    sls_queue_treeview.bind("<Left>", lambda e: "break")
    sls_queue_treeview.bind("<Right>", lambda e: "break")
    sls_queue_treeview.bind("<Up>", lambda e: "break")
    sls_queue_treeview.bind("<Down>", lambda e: "break")
    sls_queue_treeview.bind("<Return>", lambda e: "break")
    sls_queue_treeview.bind("<space>", lambda e: "break")

    sls_queue_treeview.bind("<Motion>", sls_queue_add_popup)
    lbl=Label(main_window,bg="#deca7c", font=SLS_FONT_STYLE[0] + " 20")

    sls_songlist_treeview = ttk.Treeview(sls_songlist_frame, show="tree")
    sls_songlist_treeview.pack(fill=BOTH, expand=1)

    sls_songlist_treeview.bind("<Motion>", sls_songlist_add_popup)

### ### ### UI pro tvorbu zpevniku ### ### ###
if True:
    sbk_navi_buttons_frame = Frame(navi_frame_top)
    sbk_navi_buttons_frame.rowconfigure(0, weight = 1)
    sbk_navi_buttons_frame.columnconfigure((0, 1, 2, 3), weight = 1)

    sbk_select_all_btn = Button(sbk_navi_buttons_frame, text="Vybrat vše", command=lambda: file_tree.selection_set(file_tree.get_children()))
    sbk_select_all_btn.grid(row=0, column=0, sticky="nswe")

    sbk_cancel_all_btn = Button(sbk_navi_buttons_frame, text="Zrušit vše", command=lambda: file_tree.selection_remove(*file_tree.selection()))
    sbk_cancel_all_btn.grid(row=0, column=1, sticky="nswe")

    load_table_of_contents = IntVar()
    load_table_contents_checkbox = Checkbutton(
        sbk_navi_buttons_frame,
        relief="raised",
        variable=load_table_of_contents,
        text="Vytvořit obsah",
        onvalue=1,
        offvalue=0,
    )
    load_table_contents_checkbox.grid(row=0, column=2, sticky="nswe")
    load_table_contents_checkbox.select()

    sbk_load_selected_btn = Button(sbk_navi_buttons_frame, text="Nahrát vybrané", command=sbk_load_listbox_selection)
    sbk_load_selected_btn.grid(row=0, column=3, sticky="nswe")

    sbk_edit_frame = LabelFrame(edit_and_songbook_frame, text="LATEX Editor", padx=2, pady=2)
    sbk_edit_frame.pack(side=LEFT, fill = BOTH, expand = 1)

    sbk_editor_btns_frame = Frame(sbk_edit_frame, pady=2)
    sbk_editor_btns_frame.pack(fill=BOTH)

    sbk_create_pdf_btn = Button(sbk_editor_btns_frame, text="Vytvořit PDF", command=sbk_update_pdf)
    sbk_create_pdf_btn.pack(side=RIGHT)

    sbk_latex_edit_box = scrolledtext.ScrolledText(sbk_edit_frame)
    sbk_latex_edit_box.pack(fill=BOTH, expand=1)

    sbk_edit_template_btn = Button(sbk_editor_btns_frame, text="Upravit šablonu", command=sbk_edit_tex_template)
    sbk_edit_template_btn.pack(side=LEFT)

    sbk_export_pdf_btn = Button(sbk_editor_btns_frame, text="Exportovat PDF", command=sbk_export_pdf)
    sbk_export_tex_btn = Button(sbk_editor_btns_frame, text="Exportovat TEX", command=sbk_export_tex)

    sbk_upload_template_btn = Button(sbk_editor_btns_frame, text="Nahrát", command=sbk_upload_template)

    sbk_cancel_editing_btn = Button(sbk_editor_btns_frame, text="Zrušit", command=sbk_cancel_editing)

    #

try:
    main_window.state("zoomed")
    main_window.iconbitmap(SOURCE_DIR + "icon.ico")
except:
    main_window.attributes('-zoomed', True)

# stahne do Online slozky pisne ze serveru a nejake source soubory
if have_internet():
    server_comunication(
        ["server_to_Online", "download_single_file", "download_single_file", "download_single_file", "download_songlists"],
        ["", SOURCE_DIR + LATEX_FORMAT_FILE_NAME, SOURCE_DIR + COLOR_FILE_NAME, SOURCE_DIR + HELP_TEXT_FILE_NAME, ""],
        ["", SERVER_SOURCE_LOCATION + LATEX_FORMAT_FILE_NAME, SERVER_SOURCE_LOCATION + COLOR_FILE_NAME, SERVER_SOURCE_LOCATION + HELP_TEXT_FILE_NAME, ""],
    )

    update_status("Načítání uživatelského rozhraní ...")

load_colors()
load_help_text()

### ### ### UI pro nastaveni ### ### ###
if True:
    main_settings_mode_frame = Frame(main_window)

    # napoveda    
    stg_help_frame = LabelFrame(main_settings_mode_frame, text = "Nápověda")
    stg_help_frame.pack(side = TOP, fill = X, expand = 0)

    stg_help_text_label_list = []

    for help_text in STG_HELP_TEXT_LIST:
        stg_help_text_label_list.append(Label(stg_help_frame, text = help_text, justify = LEFT))
        stg_help_text_label_list[-1].pack(side = LEFT, anchor = NW, padx = 20)

    # styl prezentace
    stg_text_style_frame = LabelFrame(main_settings_mode_frame, text = "Styl prezentace", padx = 2, pady = 2)
    stg_text_style_frame.pack(side = TOP, expand = 0, fill = X)

    stg_options_frame = LabelFrame(stg_text_style_frame, padx = 2, pady = 2, text = "Písmo")
    stg_options_frame.pack(side = LEFT, fill=BOTH)

    stg_font_combobox = ttk.Combobox(stg_options_frame)
    stg_font_combobox["values"] = stg_list_of_fonts()
    stg_font_combobox["state"] = "readonly"
    try:
        stg_font_combobox.current(stg_list_of_fonts().index(SLS_FONT_STYLE[0]))
    except:
        stg_font_combobox.current(0)
    stg_font_combobox.pack(pady = 2)
    stg_font_combobox.bind("<<ComboboxSelected>>", func=stg_update_font_style)

    stg_font_size_box = ttk.Combobox(stg_options_frame)
    stg_font_size_box["values"] = text_size_list
    stg_font_size_box["state"] = "readonly"
    try:
        stg_font_size_box.current(text_size_list.index(SLS_FONT_STYLE[1]))
    except:
        stg_font_size_box.current(0)
    stg_font_size_box.pack(pady = 2)
    stg_font_size_box.bind("<<ComboboxSelected>>", func=stg_update_font_style)
    
    stg_font_color_box = ttk.Combobox(stg_options_frame)
    stg_font_color_box["values"] = colors_list_cz
    stg_font_color_box["state"] = "readonly"
    try:
        stg_font_color_box.current([color for color in STG_COLOR_DICT.values()].index(SLS_FONT_COLOR))
    except:
        stg_font_color_box.current(0)
    stg_font_color_box.pack(pady = 2)
    stg_font_color_box.bind("<<ComboboxSelected>>", func=stg_update_font_style)

    # stin pisma
    stg_shadow_frame = LabelFrame(stg_text_style_frame, padx = 2, pady = 2, text = "Stín")
    stg_shadow_frame.pack(side = LEFT, fill = BOTH, expand = 0)

    stg_shadow_color_box = ttk.Combobox(stg_shadow_frame)
    stg_shadow_color_box["values"] = colors_list_cz
    stg_shadow_color_box["state"] = "readonly"
    try:
        stg_shadow_color_box.current([color for color in STG_COLOR_DICT.values()].index(SLS_SHADOW_COLOR))
    except:
        stg_shadow_color_box.current(0)
    stg_shadow_color_box.pack(pady = 2, side = TOP)
    stg_shadow_color_box.bind("<<ComboboxSelected>>", func=stg_update_font_style)

    stg_shadow_size_box = ttk.Combobox(stg_shadow_frame)
    stg_shadow_size_box["values"] = shadow_size_list
    stg_shadow_size_box["state"] = "readonly"
    stg_shadow_size_box.current(shadow_size_list.index(SLS_SHADOW_SIZE))
    stg_shadow_size_box.pack(pady = 2, side = TOP)
    stg_shadow_size_box.bind("<<ComboboxSelected>>", func=stg_update_font_style)

    # okraj pisma
    stg_border_frame = LabelFrame(stg_text_style_frame, padx = 2, pady = 2, text = "Okraj písma")
    stg_border_frame.pack(side = LEFT, fill = BOTH, expand = 0)
    
    stg_border_color_box = ttk.Combobox(stg_border_frame)
    stg_border_color_box["values"] = colors_list_cz
    stg_border_color_box["state"] = "readonly"
    try:
        stg_border_color_box.current([color for color in STG_COLOR_DICT.values()].index(SLS_BORDER_COLOR))
    except:
        stg_border_color_box.current(0)
    stg_border_color_box.pack(pady = 2, side = TOP)
    stg_border_color_box.bind("<<ComboboxSelected>>", func=stg_update_font_style)

    stg_border_size_box = ttk.Combobox(stg_border_frame)
    stg_border_size_box["values"] = border_size_list
    stg_border_size_box["state"] = "readonly"
    stg_border_size_box.current(border_size_list.index(SLS_BORDER_SIZE))
    stg_border_size_box.pack(pady = 2, side = TOP)
    stg_border_size_box.bind("<<ComboboxSelected>>", func=stg_update_font_style)

    stg_background_frame = LabelFrame(stg_text_style_frame, padx = 2, pady = 2, text = "Pozadí")
    stg_background_frame.pack(side = LEFT, fill = Y, expand = 0)
    
    stg_background_change_btn = Button(stg_background_frame, text = "Vybrat pozadí", command = stg_change_backgound)
    stg_background_change_btn.pack(side = TOP, fill=X, expand=0)

    stg_background_default_btn = Button(stg_background_frame, text = "Výchozí pozadí", command = stg_set_default_background)
    stg_background_default_btn.pack(side = TOP, fill=X, expand=0)

    stg_preview_frame = Frame(main_settings_mode_frame)
    stg_preview_frame.pack(fill = Y, pady = 10, expand = 1)

    stg_preview_canvas = Canvas(stg_preview_frame, highlightthickness=1, highlightcolor="grey", highlightbackground="grey")
    stg_preview_canvas.pack(fill = BOTH, expand = 1)

widgets_to_disable_enable = [
    move_song_btn,
    play_recording_btn,
    save_recording_btn,
    remove_record_btn,
    new_recording_btn,
    close_song_btn,
    traspose_up_btn,
    traspose_down_btn,
    edt_update_preview_btn,
    edit_mode_main_text_box,
    song_name_box,
    song_author_box,
    song_note_box,
    slide_order_box,
    remove_song_btn,
    rename_song_btn,
    add_sharp_btn,
    add_flat_btn,
    add_squirly_br_btn,
    add_sq_brackets_btn,
    add_rd_brackets_btn,
    add_rep_r_btn,
    add_rep_l_btn,
    add_text_note_btn,
    add_backslash_btn,
]
keybind_list = [
    ["<Control-w>", lambda event: close_song(), None, True],
    ["<Control-e>", lambda event: add_symbols("[]", True), None, True],
    ["<Control-n>", lambda event: new_song(), None, False],
    ["<Control-r>", lambda event: update_output_view(), None, True],
    ["<Control-z>", lambda event: history_undo(), None, True],
    ["<Control-y>", lambda event: history_redo(), None, True],

]  # format seznamu: [[sequence, func, bind_id, unbind with others], ...]
sls_bind_list = [
    ["<Escape>", sls_end_slideshow, None],
    ["<b>", lambda event: sls_pure_image("black"), None],
    ["<w>", lambda event: sls_pure_image("white"), None],
    ["<c>", lambda event: sls_pure_image("clear"), None],
    ["<space>", lambda event: sls_change_slide("next"), None],
    ["<Right>", lambda event: sls_change_slide("next"), None],
    ["<Left>", lambda event: sls_change_slide("prev"), None],
    ["<Down>", lambda event: sls_change_slide("next"), None],
    ["<Up>", lambda event: sls_change_slide("prev"), None],
    ["<Next>", lambda event: sls_change_slide("end"), None],
    ["<End>", lambda event: sls_change_slide("end"), None],
    ["<Prior>", lambda event: sls_change_slide("begin"), None],
    ["<Home>", lambda event: sls_change_slide("begin"), None]
]  # format seznamu: [[sequence, func, bind_id]
sls_bind_list_on_mode_change = [
    ["<F5>", sls_start_slideshow, None],
    ["<Control-Down>", lambda event: sls_change_slide("next"), None],
    ["<Control-Up>", lambda event: sls_change_slide("prev"), None]]

# nastaveni souboru s cestou ERR_LOG_PATH jako chyboveho vystupu
#sys.stderr = open(ERR_LOG_PATH, "a", encoding="utf-8") TODO

sys.stderr.write("-------------------------- "+ datetime.datetime.now().strftime("%d-%m-%Y_%H-%M-%S") + " --------------------------\n")

ttk.Style().configure("Treeview", rowheight = 25)

# nahraje latex sablonu
load_latex_template()

update_internet_status()
main_window.after(5000, call_update_internet_status)
main_window.after(1000, start_autosave)

# nacitani je hotove, tudiz se zapne GUI
main_window.config(menu=menu)

sls_update_songlist()

# aktualizuje font style podle vyberu
stg_update_font_style()

set_mode_handeler("edit")
update_status("Připraven")

main_window.mainloop()
