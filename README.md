## Summary
This repo is designed for testing controller-based ACE payloads in the NTSC-U version of _The Legend of Zelda: The Wind Waker_ (GZLE01) on a Dolphin emulator, in preparation for EJ125's Wind Waker incentive at AGDQ 2026.

The idea is to simulate whatever method will be used to inject the payload on console, which we're currently thinking will be a USB Gecko transferring bytes from a binary file to controller data at a rate of ~1 kHz.

## Contents
`main_gui.py` is an executable GUI that uses the python package `dolphin-memory-engine` (DME) to hook to a Dolphin instance and repeatedly write bytes to controller 1-4 data to simulate rapid TAS inputs, which can be used to write custom ASM payloads.

The full process is broken down into several phases:
| Phase    | Description |
|----------|-------------|
| -1       | Set controllers 2-4 before the run (manually or with GUI) |
| 0        | Trigger ACE as usual to initiate a holding loop with controllers 2-4 |
| 1        | Write bytes from `phase1.bin` to controller 2 to set up input detection & caching for phase 2 |
| 2 (main) | Write bytes from `phase2.bin` to controllers 1-4 to create main payload |
| 3        | Resume gameplay |

`payload_mods/` is a folder containing mod files like `give_all_items.txt` that can be selected when regenerating `phase2.bin` with the GUI.

### NOTE: To edit/test the main payload, you only need to edit/add files in `payload_mods/` and use the GUI

`main.ipynb` is a Jupyter notebook that accomplishes the same task as the GUI (can probably remove; the only thing I still use it for is regenerating `phase1.bin`, which you shouldn't need to edit).

`phase1_addr_instruc_pairs.txt` is used to generate the binary file `phase1.bin` (currently only done inside `main.ipynb`; do not edit `phase1.bin` unless you know what you're doing).

`helper_funcs.py` contains several functions that can do useful things like:
* Convert an ASM instruction string into its hex/binary/bytes encoding.
* Read a list of desired (address, ASM_instruction) or (address, hex) pairs from a file and output a list of ASM instructions that will perform the desired writes to those addresses.
* Convert a list of ASM instructions into a binary file for phase 1/2 whose bytes can be directly written to controller data with DME to execute the phase.

Running `python interactive_ASM_encoder.py` from a terminal will initiate a command line interface that's handy for quickly converting an ASM instruction into its hex and binary encodings; type `help` while it's running for more information.

ASM encoding is done through the python package `keystone-engine`.
It doesn't have an option for the specific Gekko architecture that the GameCube uses, but its `KS_MODE_PPC64` seems basically identical as far as I can tell (other than endianness I haven't noticed any discrepancies).

## Installation
#### 1. Clone the repo to your local machine
```
git clone https://github.com/ShadowQCD/AGDQ26-WW-incentive.git
cd <repo>
```
#### 2. Install required packages (`dolphin-memory-engine` and `keystone-engine`)
```
pip install -r requirements.txt
```
#### 3. Check repo for updates
```
git pull
```

## How to use
To open the GUI or the interactive ASM encoder, simply run
```
python main_gui.py
```
or 
```
python interactive_ASM_encoder.py
```
and follow the resulting instructions.