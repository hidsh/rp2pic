# This project is based on a blog article (https://ameblo.jp/lonetrip/entry-12763727309.html). Thanks!
#
# -----------------------------------------------------------------------------
# Low-Voltage In-Circuit Serial Programming (LV-ICSP) Class

import time
import digitalio

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
