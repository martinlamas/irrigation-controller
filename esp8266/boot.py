import gc
from machine import Pin

Pin(5, mode=Pin.OUT, value=0)

gc.collect()
