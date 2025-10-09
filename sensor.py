import time
from collections import deque
from multiprocessing.connection import Connection

# sensor specific
import datetime, time
import asyncio
import logging
import threading

from bleak import BleakScanner, BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

from bicycleinit.BicycleSensor import BicycleSensor

sensor = None
radar_mac = ''
char_uuid = ''

def bin2dec(n):
    """
    Convert floating point binary (exponent=-2) to decimal float.
    """
    fractional_part = 0.0
    if n & 1 > 0:
        fractional_part += 0.25
    if n & 2 > 0:
        fractional_part += 0.5
    return fractional_part + (n>>2)

def notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    """
    Simple notification handler which processes the data received into a
    CSV row and prints it into a file.
    """
    
    dt = datetime.datetime.now()
    dt_str = dt.strftime("%Y-%m-%d %H:%M:%S.%f")
    dt_unix = dt.timestamp()
    target_id_mask = 0b11111100 # mask that reveals first 6 bits; use '&' with value
    target_ids = [0 for x in range(6)]
    target_ranges = [0 for x in range(6)] # 6 targets, each 3 bytes (info, range, speed)
    target_speeds = [0.0 for x in range(6)]
    bin_target_speeds = ["" for x in range(6)]

    # data is a bytearray
    intdata = [x for x in data]
    j = 0 # target index
    for i, dat in enumerate(intdata[1:]): # ignore flags in pos 0
        if i%3 == 0: # each target has 3 bytes
            j = i//3
            target_ids[j] = (dat & target_id_mask)
        elif i%3 == 1:
            target_ranges[j] = dat
        else: 
            target_speeds[j] = bin2dec(dat)
            bin_target_speeds[j] = format(dat, '08b')

    data_row = [target_ids, target_ranges, target_speeds, bin_target_speeds]
    print(f"{dt_str}\t{target_ranges}\t{target_speeds}")
    sensor.write_measurement(data_row)

async def scan():
    """
    Scan for the correct Varia.
    """

    return await BleakScanner.find_device_by_address(radar_mac)


async def connect(device):
    """
    Connect to the correct Varia.
    """
    # pair with device if not already paired
    async with BleakClient(device, pair=True) as client:
        print("Varia connected.")
        await client.start_notify(char_uuid, notification_handler)
        # await asyncio.sleep(60.0)     # run for given time (in seconds)
        await asyncio.Future()  # run indefinitely
        # await client.stop_notify(RADAR_CHAR_UUID)  # use with asyncio.sleep()

async def radar():
    """
    Main radar function that coordinates communication with Varia radar.
    """

    varia = await scan() # find the BLEDevice we are looking for
    if not varia:
        logging.warning("Device not found")
        return

    await connect(varia)

def main(bicycleinit: Connection, name: str, args: dict):
   
    global sensor, char_uuid, radar_mac, worker_thread

    sensor = BicycleSensor(bicycleinit, name, args)
    sensor.write_header(['target_ids', 'target_ranges', 'target_speeds', 'bin_target_speeds'])

    radar_mac = args['address']
    char_uuid = args['char_uuid']
    
    if not (radar_mac and char_uuid):
        sensor.send_msg(f'Error reading radar MAC address or characteristics UUID from config.')

    asyncio.run(radar())
    sensor.shutdown()

if __name__ == "__main__":
    main(None, "radar", {'address': '', 'char_uuid': ''})


