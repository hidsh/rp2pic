# -----------------------------------------------------------------------------
# PIC16F1xxx LV-ICSP Programmer by Seeeduino XIAO RP2040 and CircuitPython
#
# Seeeduino XIAO RP2040      Microchip PIC12F1822
#   3V3          -----------   1 VDD
#   GND          -----------   8 VSS
#   D6 : GPO     --- 10k ---   4 RA3: MCLR
#   D8 : GPO     --- 10k ---   6 RA1: ICSPCLK
#   D7 : GPO/GPI --- 10k ---   7 RA0: ICSPDAT
#

import time
import board
import digitalio
import neopixel_write

DEVICE_LIST = {
    0x2700: {  # Device ID
        "P": [0x0000, 0x0800, 0x3FFF],  # Address, Size, Value
        "C": [0x8007, 0x0002, 0x3FFF],  # Address, Size, Value
        "D": [0xF000, 0x0100, 0x00FF],  # Address, Size, Value
        "N": "PIC12F1822",  # Device Name
    }
}


# -----------------------------------------------------------------------------
# Low-Voltage In-Circuit Serial Programming (LV-ICSP) Class


class ICSP:

    WAIT_TCLK = 200e-9  # 200 ns
    WAIT_TDLY = 1e-6  # 1 us
    WAIT_TENT = 1e-3  # 1 ms
    WAIT_TERA = 5e-3  # 5 ms

    COLUMN = 0x10

    def __init__(self, MCLR, ICSPCLK, ICSPDAT):
        self.MCLR = digitalio.DigitalInOut(MCLR)
        self.MCLR.direction = digitalio.Direction.OUTPUT
        self.ICSPCLK = digitalio.DigitalInOut(ICSPCLK)
        self.ICSPCLK.direction = digitalio.Direction.OUTPUT
        self.ICSPDAT = digitalio.DigitalInOut(ICSPDAT)
        self.ICSPDAT.direction = digitalio.Direction.OUTPUT

    # Communication Routine

    def send_bit(self, length, value):
        for i in range(length):
            # TCKH: Min 100 ns
            self.ICSPCLK.value = True
            self.ICSPDAT.value = value & 1
            # TDS: Min 100 ns
            time.sleep(self.WAIT_TCLK)
            # TCKL: Min 100 ns
            self.ICSPCLK.value = False
            # TDH: Min 100 ns
            time.sleep(self.WAIT_TCLK)
            value = value >> 1

    def send_command(self, value):
        self.send_bit(6, value)
        # TDLY: Min 1 us
        time.sleep(self.WAIT_TDLY)

    def send_data(self, value):
        self.send_bit(1, 0)
        self.send_bit(14, value)
        self.send_bit(1, 0)

    def recv_data(self):
        value = 0
        self.send_bit(1, 0)
        self.ICSPDAT.direction = digitalio.Direction.INPUT
        for i in range(14):
            # TCKH: Min 100 ns
            self.ICSPCLK.value = True
            # TCO: Max 80 ns
            time.sleep(self.WAIT_TCLK)
            value |= self.ICSPDAT.value << i
            # TCKL: Min 100 ns
            self.ICSPCLK.value = False
            time.sleep(self.WAIT_TCLK)
        self.ICSPDAT.direction = digitalio.Direction.OUTPUT
        self.send_bit(1, 0)
        return value

    def set_lvp_mode(self):
        # TENTS: Min 100 ns
        self.MCLR.value = True
        time.sleep(self.WAIT_TENT)
        # TENTH: Min 250 us
        self.MCLR.value = False
        time.sleep(self.WAIT_TENT)
        # Key Sequence: 0x4D434850 (MCHP in ASCII)
        self.send_bit(8, 0x50)
        self.send_bit(8, 0x48)
        self.send_bit(8, 0x43)
        self.send_bit(8, 0x4D)
        # Total 33 Clocks
        self.send_bit(1, 0)
        time.sleep(self.WAIT_TENT)

    def set_normal_mode(self):
        self.MCLR.value = True

    # Command Routine

    def run_load_configuration(self):
        self.send_command(0x00)
        self.send_data(0x00)

    def run_load_data_for_program_memory(self, value):
        self.send_command(0x02)
        self.send_data(value)

    def run_load_data_for_data_memory(self, value):
        self.send_command(0x03)
        self.send_data(value)

    def run_read_data_from_program_memory(self):
        self.send_command(0x04)
        return self.recv_data()

    def run_read_data_from_data_memory(self):
        self.send_command(0x05)
        return self.recv_data()

    def run_increment_address(self):
        self.send_command(0x06)

    def run_reset_address(self):
        self.send_command(0x16)

    def run_begin_internally_timed_programming(self):
        self.send_command(0x08)
        # TPINT: Max 5 ms
        time.sleep(self.WAIT_TERA)

    def run_bulk_erase_program_memory(self):
        self.send_command(0x09)
        # TERAB: Max 5 ms
        time.sleep(self.WAIT_TERA)

    def run_bulk_erase_data_memory(self):
        self.send_command(0x0B)
        # TERAB: Max 5 ms
        time.sleep(self.WAIT_TERA)

    # Read Routine

    def read_memory(self, size, run_read_data, show=True):
        base_address = 0
        data = [0] * size
        for address in range(size):
            data[address] = run_read_data()
            next_address = address + 1
            self.run_increment_address()
            if not show:
                continue
            if ((next_address % self.COLUMN) == 0) or (next_address == size):
                column_data = data[base_address:next_address]
                print_data_line(base_address, column_data)
                base_address = next_address
        return data

    def read_program_memory(self, size):
        run_read_data = self.run_read_data_from_program_memory
        self.run_reset_address()
        return self.read_memory(size, run_read_data)

    def read_configulation(self, size, show=True):
        run_read_data = self.run_read_data_from_program_memory
        self.run_load_configuration()
        return self.read_memory(size, run_read_data, show)

    def read_data_memory(self, size):
        run_read_data = self.run_read_data_from_data_memory
        self.run_reset_address()
        return self.read_memory(size, run_read_data)

    # Erase Routine

    def erase_program_memory(self):
        self.run_load_configuration()
        self.run_bulk_erase_program_memory()

    def erase_data_memory(self):
        self.run_bulk_erase_data_memory()

    # Write Routine

    def write_memory(self, data, latch, run_load_data):
        base_address = 0
        size = len(data)
        for address in range(size):
            run_load_data(data[address])
            next_address = address + 1
            if ((next_address % latch) == 0) or (next_address == size):
                self.run_begin_internally_timed_programming()
            self.run_increment_address()
            if ((next_address % self.COLUMN) == 0) or (next_address == size):
                column_data = data[base_address:next_address]
                print_data_line(base_address, column_data)
                base_address = next_address

    def write_program_memory(self, data):
        if data:
            run_load_data = self.run_load_data_for_program_memory
            self.erase_program_memory()
            self.run_reset_address()
            self.write_memory(data, 16, run_load_data)

    def write_configulation(self, data):
        if data:
            run_load_data = self.run_load_data_for_program_memory
            self.run_load_configuration()
            for i in range(7):
                self.run_increment_address()
            self.write_memory(data[0:2], 1, run_load_data)

    def write_data_memory(self, data):
        if data:
            run_load_data = self.run_load_data_for_data_memory
            self.erase_data_memory()
            self.run_reset_address()
            self.write_memory(data, 1, run_load_data)


# -----------------------------------------------------------------------------
# Sub Routine


def hexstr(data):
    return " ".join([("%04X" % value) for value in data])


def print_data_line(address, data):
    print(("%04X:" % address), hexstr(data))


def print_data(data):
    for address in range(0, len(data), ICSP.COLUMN):
        print_data_line(address, data[address : address + ICSP.COLUMN])


def verify_data(memory, config, read_data):
    print("File Data")
    data_file = read_hex_file(file, memory)
    print_data(data_file)
    print("Read Data")
    if config:
        data_read = icsp.read_configulation(11)[7:9]
    else:
        data_read = read_data(memory[1])
    if data_file == data_read:
        print("Verify OK")
    else:
        print("Verify NG")


def read_configulation():
    data = icsp.read_configulation(11, False)
    device_id = data[6] & 0x3FE0
    device_infomation = DEVICE_LIST.get(device_id)
    if device_infomation is None:
        device_name = "(Not Supported)"
    else:
        device_name = "(" + device_infomation["N"] + ")"
    # Print
    print("# Configuration")
    print("User ID Location   :", hexstr(data[0:4]))
    print("Device ID          :", hexstr([device_id]), device_name)
    print("Revision ID        :", hexstr([data[6] & 0x1F]))
    print("Configuration Word :", hexstr(data[7:9]))
    print("Calibration Word   :", hexstr(data[9:11]))
    return device_infomation


def read_hex_file(name, memory):
    memory_address = memory[0]
    memory_size = memory[1]
    memory_buffer = [memory[2]] * memory_size
    extended_linear_address = 0
    # Read File
    file = open(name, "r")
    for line in file:
        line = line.rstrip()
        # Parse Record Structure
        start_code = line[0]  #         # Start code
        byte_count = line[1:3]  #       # Byte count
        address = line[3:7]  #          # Address
        record_type = line[7:9]  #      # Record type
        data = line[9:-2]  #            # Data
        checksum = line[-2:]  #         # Checksum
        # Check
        if start_code != ":":
            print("Invalid Start Code")
            return
        if (int(byte_count, 16) * 2) != len(data):
            print("Invalid Data Length")
            return
        byte_data = [int(line[i : i + 2], 16) for i in range(1, len(line), 2)]
        if sum(byte_data) & 0xFF:
            print("Invalid Checksum")
            return
        # Handle
        if record_type == "00":  #      # Data
            absolute_address = int(extended_linear_address + address, 16) >> 1
            offset_address = absolute_address - memory_address
            if 0 <= offset_address < memory_size:
                for i in range(0, len(data), 4):
                    value = int(data[i + 2 : i + 4] + data[i : i + 2], 16)
                    memory_buffer[offset_address + (i >> 2)] = value
        elif record_type == "04":  #    # Extended Linear Address
            extended_linear_address = line[9:13]
        elif record_type == "01":  #    # End Of File
            break
        else:
            print("Invalid Record Type")
            return
    file.close()
    return memory_buffer


class LED:

    mode = 0

    def __init__(self):
        self.PWR = digitalio.DigitalInOut(board.NEOPIXEL_POWER)
        self.PWR.direction = digitalio.Direction.OUTPUT
        self.PWR.value = True
        self.DAT = digitalio.DigitalInOut(board.NEOPIXEL)
        self.DAT.direction = digitalio.Direction.OUTPUT

    def set_error(self, value):
        self.mode = 2 if value else 1

    def OFF(self):
        data = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        neopixel_write.neopixel_write(self.DAT, bytearray(data[self.mode]))

    def ON_MODE(self):  # White
        neopixel_write.neopixel_write(self.DAT, bytearray([0x30, 0x30, 0x30]))
        self.mode = 0

    def ON_READ(self):  # Green
        neopixel_write.neopixel_write(self.DAT, bytearray([0x30, 0x00, 0x00]))

    def ON_ERASE(self):  # Yellow
        neopixel_write.neopixel_write(self.DAT, bytearray([0x20, 0x40, 0x00]))

    def ON_WRITE(self):  # Red
        neopixel_write.neopixel_write(self.DAT, bytearray([0x00, 0x60, 0x00]))

    def ON_VERIFY(self):  # Cyan
        neopixel_write.neopixel_write(self.DAT, bytearray([0x20, 0x00, 0x20]))


# -----------------------------------------------------------------------------
# Main Routine


file = "image.hex"

icsp = ICSP(board.D6, board.D8, board.D7)
icsp.set_lvp_mode()
device = read_configulation()

led = LED()
led.set_error(device is None)

while True:
    led.OFF()
    print("")
    print("# PIC16F1xxx LV-ICSP Programmer")
    print("MI/MO    : Enter/Exit LV-ICSP Mode                  (White)")
    if device:
        print("RP/RD/RC : Read   Program/Data/Configuration Memory (Green)")
        print("EP/ED    : Erase  Program/Data               Memory (Yellow)")
        print("WP/WD/WC : Write  Program/Data/Configuration Memory (Red)")
        print("VP/VD/VC : Verify Program/Data/Configuration Memory (Cyan)")
    else:
        print("RC       : Read Configuration Memory                (Green)")
    print("> ", end="")
    text = input().upper()
    if text == "MI":
        led.ON_MODE()
        icsp.set_lvp_mode()
    elif text == "MO":
        led.ON_MODE()
        icsp.set_normal_mode()
        device = None
    elif text == "RC":
        led.ON_READ()
        device = read_configulation()
        led.set_error(device is None)
    elif device is None:
        print("Invalid")
    elif text == "RP":
        led.ON_READ()
        icsp.read_program_memory(device["P"][1])
    elif text == "RD":
        led.ON_READ()
        icsp.read_data_memory(device["D"][1])
    elif text == "EP":
        led.ON_ERASE()
        icsp.erase_program_memory()
    elif text == "ED":
        led.ON_ERASE()
        icsp.erase_data_memory()
    elif text == "WP":
        led.ON_WRITE()
        icsp.write_program_memory(read_hex_file(file, device["P"]))
    elif text == "WD":
        led.ON_WRITE()
        icsp.write_data_memory(read_hex_file(file, device["D"]))
    elif text == "WC":
        led.ON_WRITE()
        icsp.write_configulation(read_hex_file(file, device["C"]))
    elif text == "VP":
        led.ON_VERIFY()
        verify_data(device["P"], False, icsp.read_program_memory)
    elif text == "VD":
        led.ON_VERIFY()
        verify_data(device["D"], False, icsp.read_data_memory)
    elif text == "VC":
        led.ON_VERIFY()
        verify_data(device["C"], True, None)
    elif text == "TF":
        print("Program Memory")
        print_data(read_hex_file(file, device["P"]))
        print("Configuration Memory")
        print_data(read_hex_file(file, device["C"]))
        print("Data Memory")
        print_data(read_hex_file(file, device["D"]))
    else:
        print("Invalid")
    time.sleep(0.1)

