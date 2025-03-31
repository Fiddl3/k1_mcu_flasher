#!/usr/bin/env python3

###########################################################
# MCU Update script for Creality K1 / K1C / K1 MAX printers
###########################################################
# Pure python implementation
# v0.1
# (c) 2024 CryoZ
###########################################################

from binascii import hexlify
from io import BufferedReader
from os import SEEK_END
from pathlib import Path
import argparse
import sys
import serial
import time


# Compute simple CRC
def crc(data: bytes):
    x = 0
    for i in data:
        x = (x + i) & 0xff
    return x ^ 0xff


# Debug output
def debug(msg: str, verbose: bool):
    if not verbose:
        return
    print(msg)

# Function to display progress bar
def progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=44, fill='█', print_end="\r"):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    if iteration == total: 
      fill='▓'
    bar = fill * filled_length + '░' * (length - filled_length)

    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=print_end)
    if iteration == total:
        print()

# Handshake stage:
#  bootloader waiting 15 secs after startup for handshake, then launch app
#  if app corrupted by crc16 - bootloader waiting for handshake forever
#  ALL stages requred passing handshake stage ONCE
# send: 0x75, receive ack: 0x75
def _handshake(ser: serial.Serial, v: bool):
    result = False
    try:
        if not ser.is_open:
            debug(f'open port {ser.name}', v)
            ser.open()
        debug('send handshake', v)
        if ser.write(bytes([0x75])) == 0:
            print('Cannot write data!')
            return False
        r = ser.read(1)
        if len(r) > 0:
            debug(f'rcv data {hexlify(r)}', v)
            if r[0] == 0x75:
                debug('handshake confirmed', v)
                return True
    except serial.SerialTimeoutException:
        print(f'Timeout serial {ser.name}')
        result = False
    except serial.SerialException as e:
        print(f'Error opening serial {ser.name} with error {e}')
        result = False
    return result


# Version stage:
# bootloader checks for crc16 of app, if passed - combine hw version string (in bootloader area) and fw version string (in fw area)
# if crc16 not passed - sending 25 bytes of 0x00
# send 00ff (ff - crc), receive string (25 bytes+crc) of combined hw version and fw version
def _get_version(ser: serial.Serial, v: bool):
    result = None
    try:
        if not ser.is_open:
            debug(f'open port {ser.name}', v)
            ser.open()
        debug('send version request', v)
        if ser.write(bytes([0x00, 0xff])) == 0:
            print('Cannot write data!')
            return None
        r = ser.read(26)
        if len(r) > 0:
            debug(f'rcv data {hexlify(r)}', v)
            if len(r) == 26 and r[25] == crc(r[:-1]):
                debug(f'version received! {r[:-1]}', v)
                result = bytes(r[:-1]).decode(encoding='latin')
    except serial.SerialTimeoutException:
        print(f'Timeout serial {ser.name}')
    except serial.SerialException as e:
        print(f'Error opening serial {ser.name} with error {e}')
    return result


# Get sector size stage
#  mostly = 1, multiplier for receive buffer of firmware
# send 03fc (fc - crc), receive sector size (1 byte+crc)
def _get_sector_size(ser: serial.Serial, v: bool):
    result = None
    try:
        if not ser.is_open:
            debug(f'open port {ser.name}', v)
            ser.open()
        debug('send sectorsize request', v)
        if ser.write(bytes([0x03, 0xfc])) == 0:
            print('Cannot write data!')
            return None
        r = ser.read(2)
        if len(r) > 0:
            debug(f'rcv data {hexlify(r)}', v)
            if len(r) == 2 and r[-1] == crc(r[:-1]):
                debug(f'sector size received! {r[0]}', v)
                result = r[0]
    except serial.SerialTimeoutException:
        print(f'Timeout serial {ser.name}')
    except serial.SerialException as e:
        print(f'Error opening serial {ser.name} with error {e}')
    return result


# App start stage
# bootloader check crc16 of fw in flash, if succeded - passes program flow to fw entrypoint
# send 02fd (fd - crc), receive ack 0x75
def _app_start(ser: serial.Serial, v: bool):
    result = None
    try:
        if not ser.is_open:
            debug(f'open port {ser.name}', v)
            ser.open()
        debug('send app_start request', v)
        if ser.write(bytes([0x02, 0xfd])) == 0:
            print('Cannot write data!')
            return None
        r = ser.read(2)
        if len(r) > 0:
            debug(f'rcv data {hexlify(r)}', v)
            if r[0] == 0x75 and r[-1] == crc(r[:-1]):
                debug('app started!', v)
                result = True
            else:
                debug('app start failed!', v)
                result = False
    except serial.SerialTimeoutException:
        print(f'Timeout serial {ser.name}')
    except serial.SerialException as e:
        print(f'Error opening serial {ser.name} with error {e}')
    return result


# Flash FW stage
# receive fw by chunks, size of chunks = sector size << 16, to ram, then writes to flash.
# 1) update request: send 0xfe (fe - crc), receive ack 0x75
# 2) send fw size: send dword of size with leading crc, receive ack 0x75
# 3) send chunks by chunk-size, receive statuses:
#       0x75 - chunk succeded
#       0x20 - all firmware flashed
#       0x21 - error in write ram->rom stage
#       0x1f - bad crc of received data
def _flash_fw(ser: serial.Serial, v: bool, ss: int, f: BufferedReader):

    def fw_status_check(r):
        debug(f'[flash_update] rcv data {hexlify(r)}', v)
        if len(r) == 0:
            debug('[flash_update] no rcv data', v)
            return 2
        if r[0] == 0x75:
            debug('[flash_update] chunk flashed', v)
            return 4
        if r[0] == 0x1f:
            debug('[flash_update] bad crc received', v)
            return 3
        if r[0] == 0x21:
            debug('[flash_update] flash write error', v)
            return 0
        if r[0] == 0x20:
            debug('[flash_update] [3] flash completed', v)
            return 1

    result = 0
    buffer_size = ss * 1024
    buffer_send = bytearray(buffer_size + 1)
    f.seek(0, SEEK_END)
    size = f.tell()
    f.seek(0)

    try:
        if not ser.is_open:
            debug(f'open port {ser.name}', v)
            ser.open()

        debug('send update request', v)
        if ser.write(bytes([0x01, 0xfe])) == 0:
            print('Cannot write data!')
            return 0

        progress_bar(0, 40, prefix='Progress:', suffix='Complete')
        r = ser.read(2)
        if len(r) > 0:
            debug(f'[flash_update] [1] rcv data {hexlify(r)}', v)
            if r[0] == 0x75 and r[-1] == crc(r[:-1]):
                debug('[flash_update] [1] update request confirmed!', v)
                bsize = bytearray()
                bsize.extend(size.to_bytes(4, 'little'))
                bsize.append(crc(bsize))
                if ser.write(bsize) == 5:
                    r = ser.read(2)
                    if len(r) > 0:
                        debug(f'[flash_update] [2] rcv data {hexlify(r)}', v)
                        if len(r) == 2 and r[-1] == crc(r[:-1]):
                            if r[0] == 0x75:
                                debug('[flash_update] [2] FW size confirmed!', v)
                                debug("Starting firmware update...", v)
                                total_chunks = size // buffer_size + (1 if size % buffer_size > 0 else 0)
                                chunk_count = 0
                                for _ in range(size // buffer_size):
                                    buffer_send[:-1] = f.read(buffer_size)
                                    buffer_send[-1] = crc(buffer_send[:-1])
                                    if ser.write(buffer_send) == 0:
                                        debug('[flash_update] [3] cannot send data!', v)
                                        return 2
                                    r = ser.read(2)
                                    if len(r) == 2 and r[-1] == crc(r[:-1]):
                                        x = fw_status_check(r)
                                        if x > 3:
                                            chunk_count += 1
                                            progress_bar(chunk_count, total_chunks, prefix='Progress:', suffix='Complete')
                                            continue
                                        else:
                                            return 0
                                    else:
                                        return 0

                                size_remainder = size % buffer_size
                                if size_remainder > 0:
                                    buffer_send[:size_remainder] = f.read(size_remainder)
                                    buffer_send[size_remainder] = crc(buffer_send[:size_remainder])
                                    progress_bar((chunk_count*2)+1, total_chunks*2, prefix='Progress:', suffix='Complete')
                                    
                                    if ser.write(buffer_send[:size_remainder + 1]) == 0:
                                        debug('[flash_update] [4] cannot send data!', v)
                                        return 2
                                    r = ser.read(2)
                                    if len(r) == 2 and r[-1] == crc(r[:-1]):
                                        chunk_count += 1
                                        progress_bar(chunk_count, total_chunks, prefix='Progress:', suffix='Complete')
                                       
                                        return fw_status_check(r)
                                    else:
                                        return 0
                                else:
                                    return x
                            else:
                                return 0
                    else:
                        return 0
            else:
                debug('update request failed!', v)
                result = 2
    except serial.SerialTimeoutException:
        print(f'Timeout serial {ser.name}')
    except serial.SerialException as e:
        print(f'Error opening serial {ser.name} with error {e}')
    return result


def open_port(port):
    ser = None
    try:
        ser = serial.Serial(port, baudrate=115200, timeout=2.0)
    except serial.SerialException as e:
        print(f'Error opening serial {port} with error {e}')
    return ser


def handshake(args):
    ser = open_port(args.port)
    v = args.verbose
    result = False
    if ser:
        try:
            try:
                handshake_check = _handshake(ser, v)
                if handshake_check is not None and handshake_check:
                    return True
            except Exception as e:
                print(f'Exception! Port {args.port} with error {str(e)}')
                result = False
        finally:
            ser.close()
    else:
        print(f'Cannot open port {args.port}')
    return result


def get_version(args):
    ser = open_port(args.port)
    v = args.verbose
    result = False
    if ser:
        try:
            try:
                ver = _get_version(ser, v)
                if ver is not None:
                    print(f'FW Version: {ver}')
                    return True
            except Exception as e:
                print(f'Exception! Port {args.port} with error {str(e)}')
                result = False
        finally:
            ser.close()
    else:
        print(f'Cannot open port {args.port}')
    return result


def app_start(args):
    ser = open_port(args.port)
    v = args.verbose
    if ser:
        try:
            try:
                for retries in range(3):
                    res = _app_start(ser, v)
                    if res is not None:
                        if res == 1:
                            debug('App started', v)
                            return True
                        else:
                            debug(f'App start failed, retry #{retries+1}', v)
                debug('App start failed after 3 retries', v)
                return False
            except Exception as e:
                print(f'Exception! Port {args.port} with error {str(e)}')
        finally:
            ser.close()
    else:
        print(f'Cannot open port {args.port}')


def update(args):
    file = Path(args.file)
    if not file.is_file():
        print(f'File {args.file} is not exists')
        return False
    ser = open_port(args.port)
    v = args.verbose
    if ser:
        try:
            try:
                with open(file, 'rb') as f:
                    ss = _get_sector_size(ser, v)
                    if ss is None:
                        debug('Cannot get sector size', v)
                    else:
                        for retries in range(3):
                            res = _flash_fw(ser, v, ss, f)
                            if res is not None:
                                if res == 1:
                                    debug('Firmware updated successfully', v)
                                    return True
                                else:
                                    debug(f'FW flash failed, retry #{retries+1}', v)
                        debug('FW Update failed after 3 retries', v)
                return False
            except Exception as e:
                print(f'Exception! Port {args.port} with error {str(e)}')
        finally:
            ser.close()
    else:
        print(f'Cannot open port {args.port}')
    return False


# Request bootloader function
def request_bootloader(args):
    v = args.verbose
    
    # Check if Klipper service is active
    import subprocess
    klipper_status = subprocess.run(['systemctl', 'is-active', 'klipper'], capture_output=True, text=True)
    if klipper_status.stdout.strip() == 'active':
        user_input = input("Klipper service is active. Do you want to stop it? (y/n): ")
        if user_input.lower() != 'y':
            print("Operation cancelled by user.")
            return False
        subprocess.run(['sudo', 'systemctl', 'stop', 'klipper'])
        print("Klipper service stopped.")    
    
    ser = open_port(args.port)
    # Check if we're in bootloader mode
    ver = _get_version(ser, v)
    if ver is not None:
        print(f'Already in bootloader mode: FV: {ver}')
        return True
    ser.close()
    
    print(f"Requesting serial bootloader for device {args.port}:{args.baud}...")
    ser = None
    try:
        ser = serial.Serial(args.port, baudrate=args.baud, timeout=2.0)
    except serial.SerialException as e:
        print(f'Error opening serial {args.port} with error {e}')
    
    try:
        ser.write(b"~ \x1c Request Serial Bootloader!! ~")
        ser.close()
        # Wait for a response
        time.sleep(1)
        ser = open_port(args.port)
        # Check if we're in bootloader mode
        if _handshake(ser, v):
            ver = _get_version(ser, v)
            print(f'Successfully entered bootloader mode: FV: {ver}')
            return True
        else:
            print("Failed to enter bootloader mode")
            return False
    except serial.SerialException as e:
        print(f"Error requesting bootloader: {e}")
        return False

parser = argparse.ArgumentParser(description='Creality K1 MCU Flasher')
parser.add_argument('-v', '--verbose', action='store_true', help='Debug output')

parser.add_argument('-c', '--handshake', action='store_true', help='Attempt handshake before operation')

parser.add_argument('-i', '--port', type=str, help='serial device', required=True)

parser.add_argument('-f', '--file', type=str, help='firmware file')

parser.add_argument('-u', '--update', action='store_true', help='Update firmware from file')

parser.add_argument('-s', '--appstart', action='store_true', help='Attempt to start fw')
parser.add_argument('-g', '--version', action='store_true', help='Get version')

parser.add_argument('-r', '--request-bootloader', action='store_true', help='Request bootloader and exit (Custom Klipper build needed)')
parser.add_argument('-b', '--baud', default=230400, type=int, help='Klipper serial baudrate (for bootloader request)')
# General workflow with bootloader operations:
# 1. handshake
# 2. get version
# 3. get sector size
# 4. fw update
# 4.1 update request
# 4.2 send fw size
# 4.3 send fw
# 5. app start

args = parser.parse_args(args=None if sys.argv[1:] else ['--help'])
exit_code = 0
if args.request_bootloader:
    exit_code = request_bootloader(args)
else:
    if args.handshake:
        exit_code = handshake(args)
    if args.version:
        exit_code = get_version(args)
    if args.update:
        exit_code = update(args)
        exit_code = app_start(args)
    if args.appstart:
        exit_code = app_start(args)

sys.exit(exit_code)
