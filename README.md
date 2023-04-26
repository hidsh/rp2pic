# rp2pic

A PIC Programmer by Raspberry Pi Pico and the cousins

## Install

### 1. Install Circuitpython
1. Download Circuitpython UF2 from [https://circuitpython.org/downloads](https://circuitpython.org/downloads)

1. Press button BOOTSEL on Raspberry Pi Pico
1. Connect USB cable to Raspberry Pi Pico
1. Release button BOOTSEL on Raspberry Pi Pico
1. Copy UF2 to `RPI-RP2`
1. After a while, `CIRCUITPY` should be appeared instead of `RPI-RP2` 

### 2. Install library

1. download library bundle from [https://circuitpython.org/libraries](https://circuitpython.org/libraries).

2. copy `adafruit_datetime.mpy` in the zip into the folder `CIRCUITPY/lib`

### 3. Install rp2pic
1. copy `rp2pic.py` into `CIRCUITPY`

## Usage

rp2pic has two modes.

|Mode|`PIN_SW_AUTO`|
|Command Mode| High|
|Auto-Prog Mode| Low|

### Command Mode

Command Mode can be Program/Erase/Verify by CUI through USB serial terminal such like gnu screen, minicom, teraterm, etc.

```
# PIC16F1xxx LV-ICSP Programmer
waiting hex...
> h
Auto Prog : No
Device    : PIC16F1503
File      : 16f1503_blink_intosc.hex    2023-4-26 18:13:4

MI/MO     : Enter/Exit LV-ICSP Mode                  (White)
RP/RD/RC  : Read   Program/Data/Configuration Memory (Green)
EP/ED     : Erase  Program/Data               Memory (Yellow)
WP/WD/WC  : Write  Program/Data/Configuration Memory (Red)
VP/VD/VC  : Verify Program/Data/Configuration Memory (Cyan)
```

### Auto-Prog Mode

Auto-Prog Mode behaves as an automatic programmer.

You can program it into PIC just by Drag and Drop the hex file.
