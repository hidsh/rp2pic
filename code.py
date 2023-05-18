# ----------------------------------------------------------------------------
# PIC16F1xxx LV-ICSP Programmer by RP2040 cousins. and CircuitPython
#
# This project is based on a blog article (https://ameblo.jp/lonetrip/entry-12763727309.html). Thanks!
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
import re
import board
import digitalio
from busio import I2C
from os import stat, listdir
from adafruit_datetime import datetime

if board.board_id == 'Seeeduino XIAO RP2040':
    import neopixel_write

DEVICE_LIST = {
    0x2700: {  # Device ID
        'N': 'PIC12F1822',  # Device Name
        'P': [0x0000, 0x0800, 0x3FFF],  # Address, Size, Value
        'C': [0x8007, 0x0002, 0x3FFF],  # Address, Size, Value
        'D': [0xF000, 0x0100, 0x00FF],  # Address, Size, Value
    },
    0x1BC0: {  # Device ID
        'N': 'PIC12LF1840',  # Device Name
        'P': [0x0000, 0x1000, 0x3FFF],  # Address, Size, Value
        'C': [0x8007, 0x0002, 0x3FFF],  # Address, Size, Value
        'D': [0xF000, 0x0100, 0x00FF],  # Address, Size, Value
    },
    0x2CE0: {  # Device ID
        'N': 'PIC16F1503',  # Device Name
        'P': [0x0000, 0x0800, 0x3FFF],  # Address, Size, Value
        'C': [0x8007, 0x0002, 0x3FFF],  # Address, Size, Value
        'D': [0xF000, 0x0000, 0x00FF],  # Address, Size, Value # TODO temporary disabled, High-Endurance Flash should be supported
    },
    0x2720: {  # Device ID
        'N': 'PIC16F1823',  # Device Name
        'P': [0x0000, 0x0800, 0x3FFF],  # Address, Size, Value
        'C': [0x8007, 0x0002, 0x3FFF],  # Address, Size, Value
        'D': [0xF000, 0x0100, 0x00FF],  # Address, Size, Value
    },
    0x2300: {  # Device ID
        'N': 'PIC16F1933',  # Device Name
        'P': [0x0000, 0x0800, 0x3FFF],  # Address, Size, Value
        'C': [0x8007, 0x0002, 0x3FFF],  # Address, Size, Value
        'D': [0xF000, 0x0000, 0x00FF],  # Address, Size, Value
    },
}

# -----------------------------------------------------------------------------
# Low-Voltage In-Circuit Serial Programming (LV-ICSP) Class

class ICSP:
    WAIT_TCLK = 200e-9  # 200 ns        ;; TODO time.sleep() under usec have no accurate waiting, find another way
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
                # print_data_line(base_address, column_data)
                print('*', end='')
                base_address = next_address
        print()

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
        data_device = detector.icsp.read_configuration(11, 'config')[7:9]
    else:
        data_device = read_data(memory[1])
    if data_hex == data_device:
        prinp('Verify OK')
        return None
    else:
        prinp('Verify NG')
        return -1    # error

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

class Detector:
    device_info = dict.fromkeys(['user_id_location',
                                 'device_id',
                                 'revision_id',
                                 'configuration_word',
                                 'calibration_word',
                                 'device_name',
                                 'P',
                                 'C',
                                 'D',
                                 'i2c_slave_addr'])
    def __init__(self):
        pass
        if PIN_ICSP_MCLR and PIN_ICSP_CLK and PIN_ICSP_DAT:
            self.icsp = ICSP(PIN_ICSP_MCLR, PIN_ICSP_CLK, PIN_ICSP_DAT)

            # with NO_Printer():
            info = self.get_device_info()

            self.device_info.update(info)
        else:
            print('Error: Can not get icsp interface. Check PIN_ICSP_MCLR, PIN_ICSP_CLK, PIN_ICSP_DAT if you use programing  to PIC uC.')

        if PIN_I2C_SCL and PIN_I2C_SDA:
            self.tool_i2c = I2C_Tool(PIN_I2C_SCL, PIN_I2C_SDA)
            slaves = self.tool_i2c.cmd_scan()
            self.device_info.update({'i2c_slave_addr': slaves})
        else:
            print('Error: Can not get i2c interface. Check PIN_I2C_SCL, PIN_I2C_SCL if you use I2C Tool.')

    def get_device_info(self):
        self.icsp.set_lvp_mode()
        conf = self.icsp.read_configuration(11, False)
        self.icsp.set_normal_mode()

        device_id = conf[6] & 0x3FE0
        icsp_setting = DEVICE_LIST.get(device_id)

        device_info = {'user_id_location': hexstr(conf[0:4]),
                       'device_id': hexstr([device_id]),
                       'revision_id': hexstr([conf[6] & 0x1F]),
                       'configuration_word': hexstr(conf[7:9]),
                       'calibration_word': hexstr(conf[9:11]),
                       'device_name': icsp_setting['N'] if icsp_setting else None,
                       'P': icsp_setting['P'] if icsp_setting else None,
                       'C': icsp_setting['C'] if icsp_setting else None,
                       'D': icsp_setting['D'] if icsp_setting else None}
        return device_info

    def show_detail(self):
        di = self.device_info
        print(f"""# ICSP setting
  Device ID            : {di['device_id']}
  Device Name          : {di['device_name'] or '*** Not Supported ***'}
  Program Memory       : {di['P']}
  Data Memory          : {di['D']}
  Configuration Memory : {di['C']}

# I2C Tool setting
  I2C Slave Address    : {[hex(x) for x in di['i2c_slave_addr']] or '*** Not Detected ***'}""")

    def diagnose_icsp(self):
        ret = 0
        di = self.device_info
        if di['device_name']:
            prinp(f'Device detected, Name={di["device_name"]}, Device ID={di["device_id"]}')
        else:
            print(f'---{di["device_id"]}---')
            if di['device_id'] != '0000':
                prinp(f'Error: Wrong connection to the PIC device?')
                ret = -1
            else:
                prinp(f'Error: Not found device info. Unsupported Device ID for {hexstr(di["device_id"])}')
                ret = -2

            prinp('       All programming features can not be used until fix it.')
        return ret

    def diagnose_i2c(self):
        ret = 0
        slaves = self.device_info['i2c_slave_addr']
        if not slaves:
            prinp(f'Error: I2C slave not found. Check connection to the PIC device and try re-scanning.')
            ret = -1
        elif slaves and len(slaves) > 1:
            prinp(f'Caution: Detected multiple I2C slaves. Choose one of {slaves}')
            self.device_info['i2c_slave_addr'] = select_i2c_slave(slaves)

        return ret

    def select_i2c_slave(self, slaves):
        sel = None
        while not sel:
            s = input().upper()
            print(f'--- {s} in {slaves} ---')
            if s in [x.upper() for x in slaves]:
                sel = s

        return sel

class I2C_Tool():
    tgt_addr = None

    def __init__(self, scl, sda):
        self.i2c = I2C(scl, sda)

    def handler(self, cmd, args):
        found = [x for x in self.CMD_LIST if cmd in x[0]]
        if not found:
            print(f'Invalid Command: {cmd}')
        else:
            return found[0][1](self, args)

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

    def cmd_reset(self, args=[]):
        try:
            detector.icsp.reset()
        except NameError:
            print('Error: Cannot Reset slave device because ICSP is not available.')

    def cmd_sleep(self, args=[]):
        if not args or not args[0].isdigit():
            print("Error: Command 'sleep' needs a decimal integer argument. e.g. 'sleep 1' for sleeping 1 seconds")
            return

        time.sleep(float(args[0]))

    def cmd_print(self, args=[]):
        print(' ' + ' '.join(args) + ' ')

    def deinit(self):
        self.i2c.deinit()

    def cmd_scan(self, args=[]):
        slaves = []
        while not self.i2c.try_lock():
            pass

        try:
            slaves = self.i2c.scan()
        finally:
            self.i2c.unlock()
        return slaves           # e.g. mcp23017 = [0x20] (010_0xxx)

    def cmd_addr(self, s_args):
        if not s_args:
            print(f'Target Device: {hex(self.tgt_addr)}')
        elif len(s_args) == 1:
            if int(s_args[0], 16) in [x[2:] for x in self.cmd_scan()]:
                self.tgt_addr = int(s_args[0], 16)
                print(f'Target Device: {hex(self.tgt_addr)}')
            else:
                print(f'Error: Invalid Slave Address: {s_args[0]}')
        else:
           self.cmd_help(['addr'])

    def cmd_write(self, s_args):
        tx_data = [int(x, 16) for x in s_args]

        while not self.i2c.try_lock():
            pass

        try:
            self.i2c.writeto(self.tgt_addr, bytes(tx_data))
        finally:
            self.i2c.unlock()

        return 'NO-RESP'

    def cmd_read(self, s_args):
        if not s_args:
            sz = 1
        else:
            s_sz = s_args[-1]
            if not s_sz.isdigit():
                print(f'Error: The only parameter of the "R" command should be specifed the byte length to read as a decimal integer: {s_sz}')
                return
            sz = max(int(s_sz), 1)

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
            ret = ' '.join([f'{x:02X}' for x in rx_buf]) + err
            prinp('       => ' + ret)
        finally:
            self.i2c.unlock()

        return ret

    def cmd_write_then_read(self, s_args):
        if not s_args:
            sz = 1
        else:
            s_sz = s_args[-1]
            if not s_sz.isdigit():
                print(f'Error: The last parameter of the "WR" command should be specifed the byte length to read as a decimal integer: {s_sz}')
                return

            sz = max(int(s_sz), 1)

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
            ret = ' '.join([f'{x:02X}' for x in rx_buf]) + err
            prinp('       => ' + ret)
        finally:
            self.i2c.unlock()

        return ret

    def isfile(self, path):
        _ = list(filter(lambda x: x == path, listdir()))
        return _

    def cmd_test(self, s_args):
        if len(s_args) != 1:
            print('Error: File is not specified')
            return

        test_path = s_args[0]

        if not self.isfile(test_path):
            print(f'Error: File not found: "{test_path}"')
            return

        with open(test_path) as f:
            lines =[x.strip() for x in f.readlines()]

        RED   = '\033[91m'
        GREEN = '\033[92m'
        G = '\033[30m\033[42m'
        END   = '\033[0m'
        print('-' * 60, end='')
        func_cmd = ''
        func_param = []
        print_param = []
        test_num = 0
        cnt_ok = 0
        cnt_ng = 0
        for ln, s in enumerate(lines, start=1):
            if s == '' or s.startswith('#'):   # empty line or comment
                continue
            elif m := re.match('\=>(.*)', s):
                print('=> ', end='')
                ok = ' '.join(m.group(1).upper().split())
                with NO_Printer():
                    resp = self.handler(func_cmd, func_param)

                if resp == ok:
                    print(f'{resp:12}\t{G} PASS {END}\t{ln:8}', end='')
                    cnt_ok += 1
                else:
                    print(f'{resp:12}\t{RED} FAIL {END}\t{ln:8} Should be "{ok}"', end='')
                    cnt_ng += 1
            elif m := re.match('\?(.*)>(.*)', s):
                ps = m.group(1)
                bs1 = '\b' * len(ps)
                bs2 = ' ' * len(ps)
                print('?> ' + ps, end='')
                ok = ' '.join(m.group(2).upper().split())
                cnt_ok_old = cnt_ok
                TIMEOUT_SEC = 10
                timeout_start = now = time.monotonic()
                while now < timeout_start + TIMEOUT_SEC:
                    with NO_Printer():
                        resp = self.handler(func_cmd, func_param)

                    if resp == ok:
                        print(f'{bs1}{bs2}{bs1}{resp:12}\t{G} PASS {END}\t{ln:8}', end='')
                        cnt_ok += 1
                        break
                    now = time.monotonic()

                if cnt_ok == cnt_ok_old:
                    print(f'{bs1}{bs2}{bs1}{resp:12}\t{RED} FAIL {END}\t{ln:8} Should be "{ok}"', end='')
                    cnt_ng += 1

            else:
                ll = s.upper().split()
                func_cmd = ll[0]
                func_param = ll[1:]

                if func_cmd in ['R', 'WR']:
                    test_num += 1
                    print(f'\n{test_num:3}: {s:20} ', end='')

        print('\n' + '-' * 60)
        if cnt_ok == 0 and cnt_ng == 0:
            print(f'{RED}NO TESTS (Lines: {len(lines)}){END}')
        elif cnt_ok == cnt_ok + cnt_ng:
            print(f'{GREEN}ALL TESTS PASSED SUCCESSFULLY (Tests: {cnt_ok}, Lines: {len(lines)}){END}')
        else:
            print(f'{RED}FAILED: {cnt_ng}/{cnt_ok + cnt_ng}, Lines: {len(lines)}{END}')
        print()

    CMD_LIST = (
(['HELP', 'H', '?'], help,
'''e.g. help          : Print examples for all I2C Tool
     help w        : Print examples for "w" commands
     h             : <alias>
     ?             : <alias>'''),

(['EXIT', 'QUIT', '!!!'], None,
'''e.g. exit          : Exit from I2C Tool
     quit          : <alias>
     !!!           : <alias>'''),

(['RESET'], cmd_reset,
'''e.g. reset         : Reset target device'''),

(['SCAN'], cmd_scan,
'''e.g. scan          : Scan I2C bus then list slave addresses'''),

(['ADDR'], cmd_addr,
'''e.g. addr 42       : Set 0x42 as target device
     addr          : Show target device currently set'''),

(['W', 'S'], cmd_write,
'''e.g. w C4 2 15     : Write data "0xC4 0x02 0x15" to target device
     w             : Write to target device without any data
     s             : <alias>'''),

(['R'], cmd_read,
'''e.g. r 8           : Read 8 bytes from target device
     r             : Read 1 byte from target device'''),

(['WR'], cmd_write_then_read,
'''e.g. wr 2 C2 5 10  : Write data "0x02 0xC2 0x05" to target device,
                      then read 10 bytes from target device
     wr 10         : Write to target device without any data,
                      then read 10 bytes from target device
     wr            : Write to target device without any data,
                      then read 1 byte from target device'''),

(['SLEEP'], cmd_sleep,
'''e.g. sleep 2       : Sleep (wait for) 2 seconds'''),

(['PRINT'], cmd_print,
'''e.g. print Hello!  : Print "Hello!" ends a white space instead of
                      carriage return'''),

(['TEST'], cmd_test,
'''e.g. test i2c_1    : Start test for i2c command according to
                      the test file "i2c_1".'''))

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

def print_help(di):
    print(   f'Auto Prog : {"Yes" if auto_prog else "No"}')
    print(   f'Device    : {di["device_name"] or "*** Not Supported ***"}')
    print(   f'File      : {hex_file}\t{tstamp or ""}')
    prinp()
    ## temporary disabled ##
    # prinp(    'MI/MO     : Enter/Exit LV-ICSP Mode')
    if di['device_name']:
        prinp('# ICSP')
        prinp('  RP/RD/RC  : Read   Program/Data/Configuration Memory')
        prinp('  EP/ED     : Erase  Program/Data               Memory')
        prinp('  WP/WD/WC  : Write  Program/Data/Configuration Memory')
        prinp('  VP/VD/VC  : Verify Program/Data/Configuration Memory')
        ## temporary disabled ##
        # prinp('RC        : Read Configuration Memory')
    else:
        detector.show_detail()

    if di['i2c_slave_addr']:
        prinp()
        prinp('# Tools')
        prinp('  I2C       : I2C Tool')
        prinp('  IIC       : <alias>')
        prinp('  II        : <alias>')

class LVP_Mode:
    def __enter__(self):
        detector.icsp.set_lvp_mode()

    def __exit__(self, exc_type, exc_value, traceback):
        detector.icsp.set_normal_mode()

def proc_auto_prog():
    print('WP', end=', ')
    led.ON_WRITE()
    detector.icsp.write_program_memory(read_hex_file(hex_file, device['P']))     # WP

    print('VP', end=', ')
    led.ON_VERIFY()
    if(verify_data(device['P'], False, detector.icsp.read_program_memory)):      # VP
       return 'Error: Program memory'

    if device['D'][1] > 0:      # check data memory size
        print('WD', end=', ')
        led.ON_WRITE()
        detector.icsp.write_data_memory(read_hex_file(hex_file, device['D']))    # WD

        print('VD', end=', ')
        led.ON_VERIFY()
        if(verify_data(device['D'], False, detector.icsp.read_data_memory)):     # VD
           return 'Error: Data memory'

    print('WC', end=', ')
    led.ON_WRITE()
    detector.icsp.write_configulation(read_hex_file(hex_file, device['C']))      # WC

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
        return (hexs[max_idx], fmt_time(tstamps[max_idx]))
    else:
        return (None, None)


def check_hex_file():
    hex_path = None
    while not hex_path:
        hex_path, tstamp = get_latest_hex()
        time.sleep(0.2)
    return (hex_path, tstamp)

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
    prinp(f'Error: Unsuppored Board ID: {board.board_id}')
    halt()

with NO_Printer():
    detector = Detector()

# with NO_Printer():
# info = self.get_device_info()

# Automatic programming?
SW = digitalio.DigitalInOut(PIN_SW_AUTO)
SW.direction = digitalio.Direction.INPUT
SW.pull = digitalio.Pull.UP

led.set_error(0)
led.OFF()
led_error.OFF()

RETRY_MAX = 5

print()
print('# RP2PIC - PIC16F1xxx LV-ICSP Programmer')
print('Waiting hex file...')

while True:                 # command loop (top)
    with NO_Printer():
        hex_file, tstamp = check_hex_file()

    # auto-prog mode
    auto_prog = not SW.value    # Press (LOW) -> Auto prog:ON

    if auto_prog:
        if detector.diagnose_icsp() < 0:
            detector = Detector()
            continue                    # prints error infinitely til the proper connections

        print('Auto Prog detected.')
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

    # command mode
    print('> ', end='')
    text = input().strip().upper()
    if text in ['?', 'H', 'HELP']:
        print_help(detector.device_info)
    elif text == 'RESET':
        led.ON_MODE()
        detector.icsp.reset()
        led.set_error(0)
        led.OFF
    elif text in ['RP', 'RD', 'EP', 'ED', 'WP', 'WD', 'WC', 'VP', 'VD', 'VC', 'TF']:
        if detector.diagnose_icsp() < 0:
            detector.show_detail()
            with NO_Printer():
                detector = Detector()
            continue

        ## temporary disable ##
        # if text == 'MI':
        #     led.ON_MODE()
        #     icsp.set_lvp_mode()
        # elif text == 'MO':
        #     led.ON_MODE()
        #     icsp.set_normal_mode()
        #     device = None
        # elif text == 'RC':
        #     led.ON_READ()
        #     with LVP_Mode():
        #         device = read_configuration()
        #     led.set_error(device is None)
        elif text == 'RP':
            led.ON_READ()
            with LVP_Mode():
                detector.icsp.read_program_memory(detector.device_info['P'][1])
        elif text == 'RD':
            led.ON_READ()
            with LVP_Mode():
                detector.icsp.read_data_memory(detector.device_info['D'][1])
        elif text == 'EP':
            led.ON_ERASE()
            with LVP_Mode():
                detector.icsp.erase_program_memory()
        elif text == 'ED':
            led.ON_ERASE()
            with LVP_Mode():
                detector.icsp.erase_data_memory()
        elif text == 'WP':
            led.ON_WRITE()
            with LVP_Mode():
                detector.icsp.write_program_memory(read_hex_file(hex_file, detector.device_info['P']))
            # TODO do not overwrite configuration word
            # なぜかWPでconfiguration wordを書くとおかしくなる(WPのあとでWCで書くと問題ない)
            #  .hex Data
            #    0000: 39E4 3FFF
            #  Read Data
            #    0000: 3FFF 3FFF <--!!
            #
            # TODO: 最悪 :02 0000 04 0001 F9 から次の:02 0000 04 0001以外 まで無視するとか)
        elif text == 'WD':
            led.ON_WRITE()
            with LVP_Mode():
                detector.icsp.write_data_memory(read_hex_file(hex_file, detector.device_info['D']))
        elif text == 'WC':
            led.ON_WRITE()
            with LVP_Mode():
                detector.icsp.write_configulation(read_hex_file(hex_file, detector.device_info['C']))
        elif text == 'VP':
            led.ON_VERIFY()
            with LVP_Mode():
                verify_data(detector.device_info['P'], False, detector.icsp.read_program_memory)
        elif text == 'VD':
            led.ON_VERIFY()
            with LVP_Mode():
                verify_data(detector.device_info['D'], False, detector.icsp.read_data_memory)
        elif text == 'VC':
            led.ON_VERIFY()
            with LVP_Mode():
                verify_data(detector.device_info['C'], True, None)
        elif text == 'TF':
            data = read_hex_file(hex_file, detector.device_info['P'])
            if not data: continue
            prinp('Program Memory');        print_data(data)

            data = read_hex_file(hex_file, detector.device_info['C'])
            if not data: continue
            prinp('Configuration Memory');  print_data(data)

            data = read_hex_file(hex_file, detector.device_info['D'])
            if not data: continue
            prinp('Data Memory');           print_data(data)

    elif text in ['I2C', 'IIC', 'II']:
        tool = detector.tool_i2c
        while True:                     # command loop (I2C)
            slaves = tool.cmd_scan()
            if not slaves:
                print('No slave device')
                break

            elif len(slaves) == 1:
                tool.tgt_addr = slaves[0]       # auto setting target device address
            else:
                print(f'Choose target device: {" ".join(slaves)}')
                print('e.g. "addr 2b" to choose 0x2B as a target device address')

            print(f'I2C {hex(tool.tgt_addr)}> ', end='')
            line = input().split()
            if not line:
                continue

            cmd = line[0].upper()
            args = line[1:]
            invalid_args = [] if cmd in ['TEST', 'PRINT'] else [x for x in args if len(x) > 2]

            if invalid_args:
                print(f'Invalid Data: {" ".join(invalid_args)}')
            elif cmd in ['EXIT', 'QUIT', '!!!']:
                break

            tool.handler(cmd, args)

    elif text == '':
        pass
    else:
        prinp('Invalid Command')
    time.sleep(0.1)
