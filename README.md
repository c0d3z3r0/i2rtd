# i2rtd

Python class for talking to Realtek scalers, e.g. RTD2719.

Info from leaked datasheets and firmware sources, reverse engineering ISP tool and a lot of educated guesses and trial&error.

Tested with RTD2719(M) in a Lenovo ThinkVision P40w-20.

Note: debug functions are firmware-specific. Basic functions will probably match Realtek's reference code in most cases.

## Example usage

Find bus number:

```sh
$ ddcutil detect
...
   I2C bus:  /dev/i2c-11
   DRM connector:           card0-DP-1
   EDID synopsis:
      Mfg id:               LEN - Lenovo Group Limited
      Model:                P40w-20
...
```

```
> import i2rtd
> r = i2rtd.I2RTD(11)

# read some XFR register via ISP
> r.isp_enable(True)
> hex(r.isp_read_xfr(0x6f)[0])
'0x92'

# disable ISP mode again (resets scaler!)
> r.isp_enable(False)

# enable debug mode and read the same register via XDATA space
> hex(r.debug_read_xdata(0xff6f)[0])
'0x12'

# dump a whole block of registers, while keeping the MCU halted
> r.debug_dump_xdata(0xff00, 0x20, halt=True)
      00 01 02 03  04 05 06 07  08 09 0a 0b  0c 0d 0e 0f
      -- -- -- --  -- -- -- --  -- -- -- --  -- -- -- --
ff00: 13 00 00 48  00 00 00 00  b0 f8 f8 f8  f8 04 00 00
ff10: f8 00 f8 00  f8 00 f8 00  00 60 00 03  34 18 03 14


# dump eeprom contents
> r.debug_dump_eeprom(0x0000, 0x50, halt=True)
      00 01 02 03  04 05 06 07  08 09 0a 0b  0c 0d 0e 0f
      -- -- -- --  -- -- -- --  -- -- -- --  -- -- -- --
0000: aa 33 32 14  00 00 00 92  91 24 31 01  00 01 00 4b
0010: 00 ff ff ff  ff ff ff ff  ff ff ff ff  ff ff ff ff
0020: ff ff 12 34  56 78 9a bc  de ff ff ff  ff ff ff ff
0030: ff ff ff ff  ff ff ff ff  ff ff ff 00  0b 14 b4 64
0040: 90 ff ff ff  00 ff ff ff  ff ff ff ff  ff ff ff ff
```

## License

Copyright (c) 2024 Michael Niewöhner

This is open source software, licensed under GPLv2. See LICENSE file for details.
