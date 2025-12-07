import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from pathlib import Path
from time import sleep

import dolphin_memory_engine as DME
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC64

import helper_funcs as HF


############################################################
# CONSTANTS
############################################################
PAD1_addr = 0x803F0F34  # controller 1 C/LR data address
PAD2_addr = 0x803F0F3C  # controller 2 C/LR data address (also r12)
PAD3_addr = 0x803F0F44  # controller 3 C/LR data address
PAD4_addr = 0x803F0F4C  # controller 4 C/LR data address

payload_folder      = Path.cwd() / "payload_mods"
csv_folder          = Path.cwd() / "csv_files"


phase_1_AI_file     = "phase1_addr_instruc_pairs.txt"
phase_1_bin_file    = "phase1.bin"
phase_2_bin_file    = "phase2.bin"

phase_m1_csv_file   = csv_folder / "phase_m1.csv"
phase_1_csv_file    = csv_folder / "phase_1.csv"
phase_2_csv_file    = csv_folder / "phase_2.csv"
#phase_3_csv_file    = csv_folder / "phase_3.csv"

phase_0_csv_file    = csv_folder / "phase_0_hack.csv"
phase_3_csv_file    = csv_folder / "phase_3_hack.csv"


nop         = 0x60000000 # "no operation" instruction
button_nop  = 0x10808080 # pscmpu1 cr1, p0, p16 (basically a nop; only affects CR1 which nothing should read from. controller inputs are Start + neutral gray stick)
icbi_r12    = 0x7C0067AC # icbi r0, r12 ; invalidates instruction cache at r12=0x803F0F3C (pad 2 C/LR address)
b_42        = 0x4BFFFFF0 # branch backwards 0x10 bytes (pad 4 -> pad 2)
b_4safety   = 0x4BE24718 # branch from pad 4 -> 0x80215664 (end of dMsg_Delete)

ks = Ks(KS_ARCH_PPC, KS_MODE_PPC64)

phase1_Nreps = 10   # number of times to perform each DME write in phase 0.5-1.5 
                    # each DME write in these phases has a ~20% chance to occur while that line is being executed, so P(success) ~ (1-.2**Nreps)**Ninstructions

# GUI color scheme
BG = "#2e2e2e"
FG = "#FFFFFF"

############################################################
# LOGGING SUPPORT
############################################################
def log(msg):
    log_box.insert(tk.END, msg + "\n")
    log_box.see(tk.END)

############################################################
# DME Write Wrappers
############################################################
def my_DME_write(addr, word, pause=0.001, Nreps=1):
    addr, word = HF.addr_value_converter(addr, word, 'int')
    for _ in range(Nreps):
        DME.write_word(addr, word)
        sleep(pause)
    log(f"Wrote 0x{word:08X} to 0x{addr:08X} (x{Nreps})")

def my_DME_writes_from_csv(csv_file, Nreps=1):
    with open(csv_file,'r') as f:
        for line in f:
            PAD_addr, word = line.strip().replace(' ','').split(",")
            my_DME_write(PAD_addr, word, Nreps=Nreps)

############################################################
# HOOK TO DOLPHIN
############################################################
def hook_to_dolphin():
    log("Attempting to hook to Dolphin...")

    try:
        DME.hook()
        sleep(0.2)  # small delay so DME updates state

        if not DME.is_hooked():
            log("❌ Failed to hook to Dolphin.")
            return

        iso = DME.read_bytes(0x80000000, 6)
        if iso != b'GZLE01':
            log(f"❌ Wrong ISO detected: {iso}. Expected GZLE01.")
            return

        log("✅ Successfully hooked to Dolphin (GZLE01 detected).\n")
        
        log("Follow this procedure:")

        log("-Phase -1: Set controllers 2-4 (manually or click 'Phase -1' button)")
        log("-Phase 0:  Trigger ACE (recommended to set a save state beforehand)")
        #log("- Phase 0.5: Transition into Phase 1")
        log("-Phase 1:  Set up input detection & caching for phase 2")
        #log("- Phase 1.5: Transition into Phase 2")
        log("-Phase 2:  Write main payload from phase2.bin (select mods & regenerate first)")
        log("-Phase 3:  Resume gameplay\n")
        
        # log("Select which 'Main Payload Files' to include in Phase 2 and click 'Regenerate phase2.bin'\n")
        # log("While in holding loop, click 'Phase 0.5' - 'Phase 3' in sequence to execute payload and resume gameplay.\n")
        
        # Optional: disable the button once hooked
        #hook_btn.config(state="disabled")

    except Exception as e:
        log(f"❌ Error while hooking: {e}")

############################################################
# LOAD PAYLOAD FILES AND BUILD CHECKBOXES
############################################################
payload_vars = {}
payload_files = sorted(payload_folder.iterdir())

def rebuild_phase2_bin():
    selected_files = [f for f,v in payload_vars.items() if v.get()==1]
    log(f"Rebuilding {phase_2_bin_file} with:")
    for s in selected_files:
        log(f"  - {s.name}")

    HF.phase2_create_bin_from_files(
        selected_files,
        phase_2_bin_file,
        #input_type="hex",
        ks=ks
    )
    
    HF.phase2_bin_to_csv(phase_2_bin_file, phase_2_csv_file)
    log(f"{phase_2_bin_file}, {phase_2_csv_file} regenerated.\n")

########################################################################
# Create phase 1 binary file from file of (address, instruction) pairs
########################################################################
def rebuild_phase1_bin():
    phase1_AI_pairs = HF.get_addr_value_pairs_from_files(phase_1_AI_file, output_type='ASM', ks=ks)
    HF.phase1_create_bin(phase1_AI_pairs, phase_1_bin_file, ks=ks)
    HF.phase1_bin_to_csv(phase_1_bin_file, phase_1_csv_file)
    log(f"{phase_1_bin_file}, {phase_1_csv_file} regenerated.\n")


############################################################
############################################################
# PHASE FUNCTIONS
############################################################
############################################################

######################################################################################################
# PHASE -1 (pre-ACE): Set controllers 2-4 at start (optional, can manually set before the run instead)
######################################################################################################
def run_phase_m1():
    log("Running Phase -1...")
    # # nop out controller 2-4 button/left stick data (will be different if using unplug strats; need to test)
    # for n in range(3):
    #     button_addr = 0x803F0F38 + n*0x08
    #     my_DME_write(button_addr, button_nop)

    # my_DME_write(PAD2_addr, nop)       # clear pad 2 C/LR data
    # my_DME_write(PAD3_addr, icbi_r12)  # invalidate instruction cache at r12=0x803F0F3C so that the CPU sees updates to pad 2 C/LR data
    # my_DME_write(PAD4_addr, b_42)      # branch from pad 4 -> pad 2; main loop for phase 1
    
    my_DME_writes_from_csv(phase_m1_csv_file, Nreps=1)
    log("Phase -1 complete.\n")

######################################################################################################
# PHASE 0: Trigger ACE
######################################################################################################
def run_phase_0():
    log("Running Phase 0...")    
    # To avoid doing the full ACE setup, this directly hacks the J2DTextBox::~J2DTextBox vtable value to point to pad 2
    my_DME_writes_from_csv(phase_0_csv_file, Nreps=1)
    # Then talk to Mesa and close his last text box to trigger ACE and enter phase 1
    log("Phase 0 complete.\n")

################################################################################
# PHASE 1: Set up input detection & cache management for phase 2 (main payload)
################################################################################
def run_phase_1():
    log("Running Phase 1...")
    my_DME_writes_from_csv(phase_1_csv_file, Nreps=10)
    log("Phase 1 complete.\n")
    
    # my_DME_write(0x8039D778, 0x802D5820)
    # my_DME_write(0x803F0F4C, HF.get_ASM_encoding('bl -> 0x802D5820', addr=0x803F0F4C, ks=ks))
    

##################################################################
# PHASE 2: Write main payload using pads 1-4 and resume gameplay
##################################################################
def run_phase_2():
    log("Running Phase 2...")
    my_DME_writes_from_csv(phase_2_csv_file, Nreps=1)
    
    log("Phase 2 complete.\n")



#################################################################################################
# PHASE 3 (old, now included in phase 2): Perform any cleanup (if necessary) and resume gameplay
#################################################################################################
def run_phase_3():
    log("Running Phase 3...")
    # cleanup TBD; could zero out all addresses in phase1_AI_file but doesn't seem necessary
    # Branch to safety to resume game
    #DME.write_bytes(PAD4_addr, b_4safety)   # 0x803F0F4C: b -> 0x80215664
    # my_DME_write(0x803F0F3C, HF.get_ASM_encoding('lis r29, 0x8157', ks=ks))
    # my_DME_write(0x803F0F44, HF.get_ASM_encoding('ori r29, r29, 0x41E0', ks=ks))
    # my_DME_write(0x803F0F4C, HF.get_ASM_encoding('b -> 0x802CFF74', addr=0x803F0F4C, ks=ks))

    my_DME_writes_from_csv(phase_3_csv_file, Nreps=1)
    log("Phase 3 complete.\n")



############################################################################
############################################################################
# TKINTER GUI LAYOUT
############################################################################
############################################################################
root = tk.Tk()
root.title("Wind Waker ACE Controller Payload GUI")
root.configure(bg=BG)
############################################################
# 'Hook to Dolphin' Button
############################################################
hook_frame = tk.Frame(root, bg=BG)
hook_frame.pack(padx=10, pady=5, fill="x")

hook_btn = tk.Button(
    hook_frame,
    text="Hook to Dolphin",
    command=hook_to_dolphin,
    # bg=BG,
    # fg=FG,
    # activebackground=BG,
    # activeforeground=FG
)
hook_btn.pack()

############################################################
# Phase Buttons
############################################################
phase_frame = tk.LabelFrame(root, text="Phases", padx=10, pady=10, bg=BG, fg=FG)
phase_frame.pack(padx=10, pady=10, fill="x")

btn_m1  = tk.Button(phase_frame, text="Phase -1: Set PADs 2-4",   command=run_phase_m1)
btn_0   = tk.Button(phase_frame, text="Phase 0: Trigger ACE", command=run_phase_0)
#btn_0   = tk.Button(phase_frame, text="Phase 0: Trigger ACE", state="disabled")
#btn_05  = tk.Button(phase_frame, text="Phase 0.5", command=run_phase_05)
btn_1   = tk.Button(phase_frame, text="Phase 1: Setup",   command=run_phase_1)
#btn_15  = tk.Button(phase_frame, text="Phase 1.5", command=run_phase_15)
btn_2   = tk.Button(phase_frame, text="Phase 2: Main Payload",   command=run_phase_2)
btn_3   = tk.Button(phase_frame, text="Phase 3: Resume Game",   command=run_phase_3)

#for b in (btn_m1, btn_05, btn_1, btn_15, btn_2, btn_3):
for b in (btn_m1, btn_0, btn_1, btn_2, btn_3):
    b.pack(side="left", padx=5)


############################################################
# Mods selector frame with 'Regenerate phase2.bin' button
############################################################
files_frame = tk.LabelFrame(root, text="Main Payload Mod Files", padx=10, pady=10, bg=BG, fg=FG)
files_frame.pack(padx=10, pady=10, fill="both")

for f in payload_files:
    var = tk.IntVar(value=1)
    payload_vars[f] = var
    tk.Checkbutton(files_frame, text=f.name, variable=var,
                   bg=BG, fg=FG, selectcolor=BG, activebackground=BG, activeforeground=FG
                   ).pack(anchor='w')

regen_btn = tk.Button(files_frame, text=f"Regenerate {phase_2_bin_file}", command=rebuild_phase2_bin)
regen_btn.pack(pady=5)

#####################################
# 'Regenerate phase1.bin' button
#####################################
# regen1_btn = tk.Button(files_frame, text=f"Regenerate {phase1_bin_file}", command=rebuild_phase1_bin)
# regen1_btn.pack(side='right')

############################################################
# Log output widget
############################################################
log_frame = tk.LabelFrame(root, text="Log Output", bg=BG, fg=FG)
log_frame.pack(padx=10, pady=10, fill="both", expand=True)

log_box = tk.Text(log_frame, height=15, bg="#666666", fg="#26FF13")
log_box.pack(fill="both", expand=True)

#log("GUI Ready.")
log("Make sure ports 2-4 are set to 'None' in Dolphin controller settings.\n")
log("While game is running, click 'Hook to Dolphin' to begin.\n")

root.mainloop()
