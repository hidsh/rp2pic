# -----------------------------------------------------------------------------
# PIC16F1xxx LV-ICSP Programmer by RP2040 bros. and CircuitPython
#
# Seeeduino XIAO RP2040      Microchip PIC12F1822
#   3V3          -----------   1 VDD
#   GND          -----------   8 VSS
#   D6 : GPO     --- 10k ---   4 RA3: MCLR
#   D8 : GPO     --- 10k ---   6 RA1: ICSPCLK
#   D7 : GPO/GPI --- 10k ---   7 RA0: ICSPDAT
#
# Raspberry Pi Pico            Microchip PIC16F1503
#   3V3            -----------   1 VDD
#   GND            -----------  14 VSS
#   GP18 : GPO     --- 10k ---   4 RA3: MCLR
#   GP17 : GPO     --- 10k ---  12 RA1: ICSPCLK
#   GP16 : GPO/GPI --- 10k ---  13 RA0: ICSPDAT

import time
import board
import digitalio
from os import stat, listdir
from adafruit_datetime import datetime
from busio import I2C

if board.board_id == 'Seeeduino XIAO RP2040':
    import neopixel_write

DEVICE_LIST = {
    0x2700: {  # Device ID
        'P': [0x0000, 0x0800, 0x3FFF],  # Address, Size, Value
        'C': [0x8007, 0x0002, 0x3FFF],  # Address, Size, Value
        'D': [0xF000, 0x0100, 0x00FF],  # Address, Size, Value
        'N': 'PIC12F1822',  # Device Name
    },
    0x1BC0: {  # Device ID
        'P': [0x0000, 0x1000, 0x3FFF],  # Address, Size, Value
        'C': [0x8007, 0x0002, 0x3FFF],  # Address, Size, Value
        'D': [0xF000, 0x0100, 0x00FF],  # Address, Size, Value
        'N': 'PIC12LF1840',  # Device Name
    },
    0x2CE0: {  # Device ID
        'P': [0x0000, 0x0800, 0x3FFF],  # Address, Size, Value
        'C': [0x8007, 0x0002, 0x3FFF],  # Address, Size, Value
        'D': [0xF000, 0x0000, 0x00FF],  # Address, Size, Value # TODO temporary disabled, High-Endurance Flash should be supported
        'N': 'PIC16F1503',  # Device Name
    },
    0x2300: {  # Device ID
        'P': [0x0000, 0x0800, 0x3FFF],  # Address, Size, Value
        'C': [0x8007, 0x0002, 0x3FFF],  # Address, Size, Value
        'D': [0xF000, 0x0000, 0x00FF],  # Address, Size, Value
        'N': 'PIC16F1933',  # Device Name
    },
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

    def reset(self):
        self.MCLR.value = False
        time.sleep(0.5)
        self.MCLR.value = True
        time.sleep(0.5)

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
            if show is False:
                continue
            if ((next_address % self.COLUMN) == 0) or (next_address == size):
                column_data = data[base_address:next_address] if show != 'config' else data[7:9]    # TODO so dirty
                print_data_line(base_address, column_data)
                base_address = next_address
        return data

    def read_program_memory(self, size):
        run_read_data = self.run_read_data_from_program_memory
        self.run_reset_address()
        return self.read_memory(size, run_read_data)

    def read_configuration(self, size, show=True):
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
    return ' '.join([('%04X' % value) for value in data])


def print_data_line(address, data):
    prinp(('%04X:' % address), hexstr(data))


def print_data(data):
    for address in range(0, len(data), ICSP.COLUMN):
        print_data_line(address, data[address : address + ICSP.COLUMN])


def verify_data(memory, config, read_data):
    prinp('Hex File')
    data_hex = read_hex_file(hex_file, memory)
    print_data(data_hex)
    prinp('Device')
    if config:
        data_device = icsp.read_configuration(11, 'config')[7:9]
    else:
        data_device = read_data(memory[1])
    if data_hex == data_device:
        prinp('Verify OK')
        return None
    else:
        prinp('Verify NG')
        return -1    # error


def read_configuration():
    data = icsp.read_configuration(11, False)
    device_id = data[6] & 0x3FE0
    device_infomation = DEVICE_LIST.get(device_id)
    if device_infomation is None:
        device_name = '(Not Supported)'
    else:
        device_name = '(' + device_infomation['N'] + ')'
    # Print
    prinp('# Configuration')
    prinp('User ID Location   :', hexstr(data[0:4]))
    prinp('Device ID          :', hexstr([device_id]), device_name)
    prinp('Revision ID        :', hexstr([data[6] & 0x1F]))
    prinp('Configuration Word :', hexstr(data[7:9]))
    prinp('Calibration Word   :', hexstr(data[9:11]))
    return device_infomation


def read_hex_file(name, memory):
    memory_address = memory[0]
    memory_size = memory[1]
    memory_buffer = [memory[2]] * memory_size
    extended_linear_address = '0000'
    # Read File
    file = open(name, 'r')
    for line in file:
        line = line.rstrip()
        # Parse Record Structure
        start_code = line[0]            # Start code
        byte_count = line[1:3]          # Byte count
        address = line[3:7]             # Address
        record_type = line[7:9]         # Record type
        data = line[9:-2]               # Data
        checksum = line[-2:]            # Checksum
        # if len(data) == 4: #debug
        #    prinp(f'debug data:{data}')

        # Check
        if start_code != ':':
            prinp('Invalid Start Code')
            return
        if (int(byte_count, 16) * 2) != len(data):
            prinp('Invalid Data Length')
            return
        byte_data = [int(line[i : i + 2], 16) for i in range(1, len(line), 2)]
        if sum(byte_data) & 0xFF:   # todo diff byte_data vs checksum
            prinp('Invalid Checksum')
            return
        # Handle
        if record_type == '00':         # Data
            # prinp(f'{extended_linear_address}, {address}') # debug
            absolute_address = int(extended_linear_address + address, 16) >> 1
            offset_address = absolute_address - memory_address
            if 0 <= offset_address < memory_size:
                for i in range(0, len(data), 4):
                    # if len(memory_buffer) == 2: #debug
                    #    prinp(f'debug data:{data}')
                    value = int(data[i + 2 : i + 4] + data[i : i + 2], 16)
                    memory_buffer[offset_address + (i >> 2)] = value
        elif record_type == '04':       # Extended Linear Address
            extended_linear_address = line[9:13]
        elif record_type == '02':       # Extended Segment address
            # TODO: ignored temporary
            continue
        elif record_type == '01':       # End Of File
            break
        else:
            prinp(f'Invalid Record Type:{record_type}')
            return
    file.close()
    # if len(memory_buffer) == 2:     #debug
    #    prinp(f'debug memory_buffer:{memory_buffer}')
    return memory_buffer


class LED_MONO:
    mode = 0

    def __init__(self, pin):
        dio = digitalio.DigitalInOut(pin)
        dio.direction = digitalio.Direction.OUTPUT
        dio.value = True
        self.dio = dio
        self.OFF()

    def set_error(self, value):
        self.mode = 2 if value else 1

    def OFF(self):
        self.dio.value = (self.mode == 2)

    def ON(self):
        self.dio.value = True

    def ON_MODE(self):
        self.dio.value = True
        self.mode = 0

    def ON_READ(self):
        self.dio.value = True
        pass

    def ON_ERASE(self):
        self.dio.value = True
        pass

    def ON_WRITE(self):
        self.dio.value = True
        pass

    def ON_VERIFY(self):
        self.dio.value = True
        pass


class LED_NEOPIXEL:
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

class I2C_Util:
    tgt_addr = None

    def __init__(self, scl, sda):
        self.i2c = I2C(scl, sda)

    def handler(self, cmd, args):
        found = [x for x in self.CMD_LIST if cmd in x[0]]
        if not found:
            print(f'Invalid Command: {cmd}')
        else:
            found[0][1](self, args)

    def help(self, args):
        if not args:
            txt = '\n'.join([x[2] for x in self.CMD_LIST])
            print(txt)
        else:
            cmd = args[0]
            found = [x for x in self.CMD_LIST if cmd in x[0]]
            if not found:
                print(f'Invalid Command: {cmd}')
            else:
                print(found[0][2])

    def deinit(self):
        self.i2c.deinit()
        del self.i2c

    def scan(self, args=[]):
        slaves = []
        while not self.i2c.try_lock():
            pass

        try:
            slaves = self.i2c.scan()
        finally:
            self.i2c.unlock()
        return slaves           # e.g. mcp23017 = [0x20] (010_0xxx)

    def addr(self, s_args):
        if not s_args:
            print(f'Target Device: {hex(self.tgt_addr)}')
        elif len(s_args) == 1:
            if int(s_args[0], 16) in [x[2:] for x in self.scan()]:
                self.tgt_addr = int(s_args[0], 16)
                print(f'Target Device: {hex(self.tgt_addr)}')
            else:
                print(f'Error: Invalid Slave Address: {s_args[0]}')
        else:
           self.help(['addr'])

    def write(self, s_args):
        tx_data = [int(x, 16) for x in s_args]

        while not self.i2c.try_lock():
            pass

        try:
            self.i2c.writeto(self.tgt_addr, bytes(tx_data))
        finally:
            self.i2c.unlock()

    def read(self, s_args):
        if not s_args:
            sz = 1
        else:
            sz = max(int(s_args[0]), 1)

        rx_buf = bytearray(sz)
        err=''

        while not self.i2c.try_lock():
            pass

        try:
            self.i2c.readfrom_into(self.tgt_addr, rx_buf)
        except OSError:
            err = ' ...Error!'
        except RuntimeError as e:
            print('Error: I2C not respond, need "reset"')
        except TimeoutError as e:
            print('Error: I2C Timeout, need "reset"')
        else:
            print(' => ' + ' '.join([f'{x:02X}' for x in rx_buf]) + err)
        finally:
            self.i2c.unlock()

    def write_then_read(self, s_args):
        if not s_args:
            sz = 1
        else:
            sz = max(int(s_args[-1]), 1)

        rx_buf = bytearray(sz)
        tx_data = [int(x, 16) for x in s_args[:-1]]
        err=''

        while not self.i2c.try_lock():
            pass

        try:
            self.i2c.writeto_then_readfrom(self.tgt_addr, bytes(tx_data), in_buffer=rx_buf)
        except OSError as e:
            err = ' ...Error!'
        except RuntimeError as e:
            print('Error: I2C not respond, need "reset"')
        except TimeoutError as e:
            print('Error: I2C Timeout, need "reset"')
        else:
            print(' => ' + ' '.join([f'{x:02X}' for x in rx_buf]) + err)
        finally:
            self.i2c.unlock()

    CMD_LIST = (
(['HELP', 'H', '?'], help,
'''e.g. help          : Print examples for all I2C Utility
     help w        : Print examples for "w" commands
     h             : <alias>
     ?             : <alias>'''),
(['EXIT', 'QUIT', '!!!'], None,
'''e.g. exit          : Exit from I2C Utility
     quit          : <alias>
     !!!           : <alias>'''),
(['RESET'], ICSP.reset,
'''e.g. reset         : Reset target device'''),
(['SCAN'], scan,
'''e.g. scan          : Scan I2C bus then list slave addresses'''),
(['ADDR'], addr,
'''e.g. addr 42       : Set 0x42 as target device
     addr          : Show target device currently set'''),
(['W', 'S'], write,
'''e.g. w C4 2 15     : Write data "0xC4 0x02 0x15" to target device
     w             : Write to target device without any data
     s             : <alias>'''),
(['R'], read,
'''e.g. r 8           : Read 8 bytes from target device
     r             : Read 1 byte from target device'''),
(['WR'], write_then_read,
'''e.g. wr 2 C2 5 10  : Write data "0x02 0xC2 0x05" to target device,
                   :  then read 10 bytes from target device
     wr 10         : Write to target device without any data,
                   :  then read 10 bytes from target device
     wr            : Write to target device without any data,
                   :  then read 1 byte from target device'''))

class NO_Printer:
    def __enter__(self):
        global prinp
        self.func_orig = prinp
        prinp = self.nop

    def __exit__(self, exc_type, exc_value, tracebak):
        global prinp
        prinp = self.func_orig
    def nop(*objs, sep='', end='\n'):
        pass

def prinp(*objs, sep='', end='\n'):
    print(*objs, sep=sep, end=end)

def print_help():
    print(   f'Auto Prog : {'Yes' if auto_prog else 'No'}')
    print(   f'Device    : {device["N"]}')
    print(   f'File      : {hex_file}\t{tstamp or ""}')
    prinp()
    prinp(    'MI/MO     : Enter/Exit LV-ICSP Mode                  (White)')
    if device:
        prinp('RP/RD/RC  : Read   Program/Data/Configuration Memory (Green)')
        prinp('EP/ED     : Erase  Program/Data               Memory (Yellow)')
        prinp('WP/WD/WC  : Write  Program/Data/Configuration Memory (Red)')
        prinp('VP/VD/VC  : Verify Program/Data/Configuration Memory (Cyan)')
    else:
        prinp('RC        : Read Configuration Memory                (Green)')
        prinp('# Utilities')
        prinp('I2C       : I2C Utility')
        prinp('I2        : <alias>')

class LVP_Mode:
    def __enter__(self):
        icsp.set_lvp_mode()

    def __exit__(self, exc_type, exc_value, traceback):
        icsp.set_normal_mode()

def proc_auto_prog():
    print('WP', end=', ')
    led.ON_WRITE()
    icsp.write_program_memory(read_hex_file(hex_file, device['P']))     # WP

    print('VP', end=', ')
    led.ON_VERIFY()
    if(verify_data(device['P'], False, icsp.read_program_memory)):      # VP
       return 'Error: Program memory'

    if device['D'][1] > 0:      # check data memory size
        print('WD', end=', ')
        led.ON_WRITE()
        icsp.write_data_memory(read_hex_file(hex_file, device['D']))    # WD

        print('VD', end=', ')
        led.ON_VERIFY()
        if(verify_data(device['D'], False, icsp.read_data_memory)):     # VD
           return 'Error: Data memory'

    print('WC', end=', ')
    led.ON_WRITE()
    icsp.write_configulation(read_hex_file(hex_file, device['C']))      # WC

    print('VC', end=', ')
    led.ON_VERIFY()
    if(verify_data(device['C'], True, None)):                           # VC
       return 'Error: Config memory'

    return None    # None: success

def fmt_time(itime):
    dt = datetime.fromtimestamp(itime)
    return f'{dt.year}-{dt.month}-{dt.day} {dt.hour}:{dt.minute}:{dt.second}'

def list_hex_file():
    return filter(lambda x: len(x) > 5 and x[-4:].lower() == '.hex', listdir())

def get_latest_hex():
    hexs = list(list_hex_file())
    if hexs:
        tstamps = [stat(x)[8] for x in hexs]    # mtime
        max_idx = tstamps.index(max(tstamps))
        prinp(tstamps[max_idx])
        return (hexs[max_idx], fmt_time(tstamps[max_idx]))
    else:
        return (None, None)

def halt():
    while True:
        time.sleep(1)

# -----------------------------------------------------------------------------
# Main Routine

if board.board_id == 'Seeeduino XIAO RP2040':
    PIN_ICSP_MCLR = board.D6
    PIN_ICSP_CLK = board.D8
    PIN_ICSP_DAT = board.D7
    PIN_SW_AUTO = board.D3
    led_error = LED_MONO(board.D2)
    led = LED_NEOPIXEL()

    PIN_I2C_SCL = board.D5
    PIN_I2C_SDA = board.D4

elif board.board_id == 'raspberry_pi_pico':
    PIN_ICSP_MCLR = board.GP18
    PIN_ICSP_CLK = board.GP17
    PIN_ICSP_DAT = board.GP16
    PIN_SW_AUTO = board.GP14
    led_error = LED_MONO(board.GP15)
    led = LED_MONO(board.LED)

    PIN_I2C_SCL = board.GP13
    PIN_I2C_SDA = board.GP12

else:
    prinp(f'Unsuppored Board ID:{board.board_id}')
    while True:
        pass

icsp = ICSP(PIN_ICSP_MCLR, PIN_ICSP_CLK, PIN_ICSP_DAT)

# Automatic programming?
SW = digitalio.DigitalInOut(PIN_SW_AUTO)
SW.direction = digitalio.Direction.INPUT
SW.pull = digitalio.Pull.UP

led.set_error(0)
led.OFF()
led_error.OFF()

RETRY_MAX = 5

print()
print('# PIC16F1xxx LV-ICSP Programmer')
while True:                 # command loop (top)
    hex_file = ''
    while not hex_file:
        with NO_Printer():
            hex_file, tstamp = get_latest_hex()
        time.sleep(0.2)

    device = None
    retry_count = 0
    while not device and retry_count < RETRY_MAX:
        led.set_error(1)
        with LVP_Mode():
            with NO_Printer():
                device = read_configuration()
        time.sleep(0.2)
        retry_count += 1

    if not device:
        with LVP_Mode():
            device = read_configuration()
        raise RuntimeError('Error while read_configuration. Unsupported Device ID?')

    auto_prog = not SW.value    # Press (LOW) --> Auto prog:ON
    if auto_prog:
        print(f'Programming {hex_file}... ', end='')
        with LVP_Mode():
            result = proc_auto_prog()

        if result:
            print('Failed')
            led.set_error(2)
            led_error.ON()
        else:
            print('Done')
            led.set_error(0)
            led.OFF()

        halt()                  # wait updating files content or reset

    # Manual commands
    print('> ', end='')
    text = input().upper()
    if text in ['?', 'H', 'HELP']:
        print_help()
    elif text == 'RESET':
        led.ON_MODE()
        icsp.reset()
        led.set_error(0)
        led.OFF()
    elif text == 'MI':
        led.ON_MODE()
        icsp.set_lvp_mode()
    elif text == 'MO':
        led.ON_MODE()
        icsp.set_normal_mode()
        device = None
    elif text == 'RC':
        led.ON_READ()
        with LVP_Mode():
            device = read_configuration()
        led.set_error(device is None)
    elif text == 'RP':
        led.ON_READ()
        with LVP_Mode():
            icsp.read_program_memory(device['P'][1])
    elif text == 'RD':
        led.ON_READ()
        with LVP_Mode():
            icsp.read_data_memory(device['D'][1])
    elif text == 'EP':
        led.ON_ERASE()
        with LVP_Mode():
            icsp.erase_program_memory()
    elif text == 'ED':
        led.ON_ERASE()
        with LVP_Mode():
            icsp.erase_data_memory()
    elif text == 'WP':
        led.ON_WRITE()
        with LVP_Mode():
            icsp.write_program_memory(read_hex_file(hex_file, device['P']))
        # TODO do not overwrite configuration word
        # なぜかWPでconfiguration wordを書くとおかしくなる(WPのあとでWCで書くと問題ない)
        #  File Data
        #    0000: 39E4 3FFF
        #  Read Data
        #    0000: 3FFF 3FFF <--!!
        # 最悪 :02 0000 04 0001 F9 から次の:02 0000 04 0001以外 まで無視するとか)
    elif text == 'WD':
        led.ON_WRITE()
        with LVP_Mode():
            icsp.write_data_memory(read_hex_file(hex_file, device['D']))
    elif text == 'WC':
        led.ON_WRITE()
        with LVP_Mode():
            icsp.write_configulation(read_hex_file(hex_file, device['C']))
    elif text == 'VP':
        led.ON_VERIFY()
        with LVP_Mode():
            verify_data(device['P'], False, icsp.read_program_memory)
    elif text == 'VD':
        led.ON_VERIFY()
        with LVP_Mode():
            verify_data(device['D'], False, icsp.read_data_memory)
    elif text == 'VC':
        led.ON_VERIFY()
        with LVP_Mode():
            verify_data(device['C'], True, None)
    elif text == 'TF':
        data = read_hex_file(hex_file, device['P'])
        if not data: continue
        prinp('Program Memory');        print_data(data)

        data = read_hex_file(hex_file, device['C'])
        if not data: continue
        prinp('Configuration Memory');  print_data(data)

        data = read_hex_file(hex_file, device['D'])
        if not data: continue
        prinp('Data Memory');           print_data(data)

    elif text in ["I2C", "I2"]:
        util = I2C_Util(PIN_I2C_SCL, PIN_I2C_SDA)
        while True:                     # command loop (I2C)
            slaves = util.scan()
            if not slaves:
                print('No slave device')
            elif len(slaves) == 1:
                util.tgt_addr = slaves[0]       # auto setting target device address
            else:
                print(f'Choose target (Slave address): {" ".join(slaves)}')
                print('e.g. "addr 2b" to choose 0x2B as a target device address')

            print('I2C> ', end='')
            line = input().upper().split()
            cmd = line[0]
            args = line[1:]
            invalid_args = [x for x in args if len(x) > 2]

            if invalid_args:
                print(f'Invalid Data: {" ".join(invalid_args)}')
            elif cmd in ['EXIT', 'QUIT', '!!!']:
                util.deinit()
                del util
                break
            elif cmd == '':
                continue

            util.handler(cmd, args)

    elif text == '':
        pass
    else:
        prinp('Invalid Command')
    time.sleep(0.1)

