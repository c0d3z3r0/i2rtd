#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

__title__       = "i2rtd"
__description__ = "Python class for talking to Realtek scalers, e.g. RTD2719"
__author__      = "Michael Niewöhner"
__email__       = "foss@mniewoehner.de"
__license__     = 'GPL-2.0-or-later'
__copyright__   = 'Copyright (c) 2024 Michael Niewöhner'

import time
from functools import partialmethod, wraps
from enum import IntEnum
from collections.abc import Iterable
from smbus2 import SMBus, i2c_msg
from pyhexdump import hexdump

R = i2c_msg.read
W = i2c_msg.write
SMBus.transfer = SMBus.i2c_rdwr

class ADDR(IntEnum):
    DBG = 0x6a >> 1
    DDC = 0x6e >> 1
    ISP = 0x94 >> 1

# todo flash, crc

#class VCP(IntEnum):
#    DEBUGEN = 0x71
#
#class CMD(IntEnum):
#    # DEBUG
#    HALT  = 0x80
#    DEBUGEN = 0x71

def debug(func, *args, **kwargs):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.debug_enabled:
            raise(Exception("Error: method requires debug mode"))

        return func(self, *args, **kwargs)

    return wrapper

def isp(func, *args, **kwargs):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.isp_enabled:
            raise(Exception("Error: method requires isp mode"))

        return func(self, *args, **kwargs)

    return wrapper

def limit_addr(_min, _max):
    def dec_limit_addr(func):
        @wraps(func)
        def wrapper(self, addr, len_data=1, *args, **kwargs):
            if not _min <= addr <= _max:
                name = func.__name__.split("_")[0].upper()
                raise(Exception(f"Error: {name} start address invalid. Range is {_min} <= addr <= {_max}"))

            max_addr = addr + (len_data if '_read_' in func.__name__ else len(len_data)) - 1
            if not _min <= max_addr <= _max:
                name = func.__name__.split("_")[0].upper()
                raise(Exception(f"Error: {name} end address invalid. Range is {_min} <= addr <= {_max}"))

            return func(self, addr, len_data, *args, **kwargs)
        return wrapper
    return dec_limit_addr

class I2RTD:
    def __init__(self, bus):
        self.bus = SMBus(bus)
        self._halted = False

        try:
            # ISP should always respond
            self.bus.read_byte(ADDR.ISP)
            # ... fail, if not
        except OSError as e:
            raise(Exception("device not reachable"))
            raise(e)

    def isp_enable(self, onoff, force=False):
        if self.isp_enabled == onoff and not force:
            return

        if onoff:
            self.bus.transfer(W(ADDR.ISP, [0x6f, 0x80]))
        else:
            self.bus.transfer(W(ADDR.ISP, [0x6f, 0x00]))

    @property
    def isp_enabled(self):
        m = R(ADDR.ISP, 1)
        self.bus.transfer(W(ADDR.ISP, [0x6f]), m)
        return bool(int.from_bytes(m) & 0x80)

    @isp
    @limit_addr(0x00, 0xff)
    def isp_iter_read_xfr(self, addr, _len=1):
        for _addr in range(addr, addr + _len):
            m = R(ADDR.ISP, 1)
            self.bus.transfer(W(ADDR.ISP, [_addr]))
            self.bus.transfer(m)
            yield int.from_bytes(m)

    def isp_read_xfr(self, addr, _len=1):
        return list(self.debug_iter_read_xfr(addr, _len))

    def isp_dump_xfr(self, addr, _len=1, end=0):
        if end:
            _len = end - addr + 1

        hexdump(self.debug_iter_read_xfr(addr, _len, halt), start_addr=addr, addr_len=1)

    @isp
    @limit_addr(0x00, 0xff)
    def isp_write_xfr(self, addr, data):
        if not isinstance(data, Iterable): raise(Exception("data must be iterable"))

        for _addr, val in enumerate(data, addr):
            self.bus.transfer(W(ADDR.ISP, [_addr, val]))

    def isp_reset(self):
        self.isp_enable(True, force=True)
        # reset mcu and scalar
        self.bus.transfer(W(ADDR.ISP, [0xee, 0x03]))

    @property
    def debug_enabled(self):
        try:
            self.bus.read_byte(ADDR.DBG)
            return True
        except OSError:
            return False

    def debug_enable(self, onoff, force=False):
        if self.debug_enabled == onoff and not force:
            return

        if not onoff and self._halted:
            raise(Exception("Debug must not be disabled when MCU is halted!"))

        time.sleep(0.05)

        if onoff:
            #self.bus.transfer(W(ADDR.DDC, [VCP.DEBUGEN, 0x81, 0xaa, 0xff]))
            self.bus.transfer(W(ADDR.DDC, [0x71, 0x81, 0xaa, 0xff]))
           #alternative:
           #self.bus.transfer(W(ADDR.DDC, [0x71, 0x82, 0x77, 0xaa, 0xff]))
        else:
            #self.bus.transfer(W(ADDR.DBG, [VCP.DEBUGEN, 0x00]))
            self.bus.transfer(W(ADDR.DBG, [0x71, 0x00]))

        time.sleep(0.05)

    @debug
    def debug_halt_mcu(self, halt):
        time.sleep(0.1)
        self.bus.transfer(W(ADDR.DBG, [0x80, int(halt)]))
        self._halted = halt
        time.sleep(0.1)

    @debug
    @limit_addr(0x0000, 0xffff)
    def debug_iter_read_xdata(self, addr, _len=1, end=0, halt=True):
        if halt:
            self.debug_halt_mcu(True)

        for _addr in range(addr, addr + _len):
            m = R(ADDR.DBG, 1)
            addrH, addrL = _addr >> 8 & 0xff, _addr & 0xff
            self.bus.transfer(W(ADDR.DBG, [0x3a, addrL, addrH]))
            if not halt:
                time.sleep(0.01)
            self.bus.transfer(m)
            yield int.from_bytes(m)

        if halt:
            self.debug_halt_mcu(False)

    def debug_read_xdata(self, addr, _len=1, halt=True):
        return list(self.debug_iter_read_xdata(addr, _len, halt))

    def debug_dump_xdata(self, addr, _len=1, end=0, halt=True):
        if end:
            _len = end - addr + 1

        hexdump(self.debug_iter_read_xdata(addr, _len, halt=halt), start_addr=addr, addr_len=2)

    @debug
    @limit_addr(0x0000, 0xffff)
    def debug_write_xdata(self, addr, data, halt=True):
        if not isinstance(data, Iterable): raise(Exception("data must be iterable"))

        if halt:
            self.debug_halt_mcu(True)

        for _addr, val in enumerate(data, addr):
            addrH, addrL = _addr >> 8 & 0xff, _addr & 0xff
            self.bus.transfer(W(ADDR.DBG, [0x3b, addrL, addrH, val]))
            if not halt:
                time.sleep(0.01)

        if halt:
            self.debug_halt_mcu(False)

    @debug
    def debug_iter_read_eeprom(self, addr, _len=1, i2caddr=0xa0, halt=True):
        if halt:
            self.debug_halt_mcu(True)

        for _addr in range(addr, addr + _len):
            addrH, addrL = _addr >> 8 & 0xff, _addr & 0xff
            m = R(ADDR.DBG, 1)
            self.bus.transfer(W(ADDR.DBG, [0x44, addrL, i2caddr, 0x00, addrH]))
            time.sleep(0.01)
            if not halt:
                time.sleep(0.01)
            self.bus.transfer(m)
            yield int.from_bytes(m)

        if halt:
            self.debug_halt_mcu(False)

    def debug_read_eeprom(self, addr, _len=1, halt=True):
        return list(self.debug_iter_read_eeprom(addr, _len, halt=halt))

    def debug_dump_eeprom(self, addr, _len=1, end=0, halt=True):
        if end:
            _len = end - addr + 1

        hexdump(self.debug_iter_read_eeprom(addr, _len, halt=halt), start_addr=addr, addr_len=4)

    @debug
    def debug_write_eeprom(self, addr, data, i2caddr=0xa0, halt=True):
        if not isinstance(data, Iterable): raise(Exception("data must be iterable"))

        if halt:
            self.debug_halt_mcu(True)

        for _addr, val in enumerate(data, addr):
            addrH, addrL = _addr >> 8 & 0xff, _addr & 0xff
            self.bus.transfer(W(ADDR.DBG, [0x04, addrL, i2caddr, val, addrH]))
            time.sleep(0.01)
            if not halt:
                time.sleep(0.01)

        if halt:
            self.debug_halt_mcu(False)

