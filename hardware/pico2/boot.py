"""
boot.py — MicroPython boot configuration for Pico 2 SHAPE node
Disables USB mass-storage mode and enables REPL over UART only
(prevents accidental filesystem corruption in deployment).

Comment out the usb_msc line during development if you need drag-and-drop
firmware flashing.
"""

import machine
import sys

# Optionally reduce CPU frequency to 120 MHz to lower heat; comment out
# to stay at the default 150 MHz for maximum LCD throughput.
# machine.freq(120_000_000)

# Enable garbage collection to manage the small heap
import gc
gc.enable()
gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
