# Creality K1 MCU Flasher

## Overview

This utility is a pure Python implementation for flashing firmware on Creality K1 series printers (K1, K1C, K1 MAX). Designed to be fully compatible with the official `mcu_util` tool, it supports operations such as handshake initiation, firmware version retrieval, firmware updates, application startup, and even direct bootloader requests (requires a custom Klipper build).

## Key Notes

- The bootloader waits for a handshake for 15 seconds after MCU power up.
- A handshake is required only once per session before performing any operation.
- For firmware flashing, ensure you power cycle the MCU before initiating the update or include the update command within your initialization script.

## Command-Line Options

| Option                         | Description                                                                                                                                                 | Example Command                                                       |
|--------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| `-v`, `--verbose`              | Enable debug output for detailed log messages.                                                                                                              | `mcu_util.py -v -c -i /dev/ttyS1`                                       |
| `-c`, `--handshake`            | Send a handshake signal (0x75) to the MCU. This step must be completed before any other operation.                                                       | `mcu_util.py -c -i /dev/ttyS1`                                          |
| `-i`, `--port`                 | Specify the serial device to connect to (this option is required).                                                                                          | `-i /dev/ttyS1`                                                       |
| `-f`, `--file`                 | Provide the firmware file for the update process.                                                                                                           | `-f /usr/data/klipper/fw/K1/bed_klipper.bin`                           |
| `-u`, `--update`               | Update (flash) the firmware using the file provided with the `-f` option.                                                                                    | `mcu_util.py -c -i /dev/ttyS1 -u -f /path/to/firmware.bin`               |
| `-s`, `--appstart`             | Attempt to start the firmware application if it has not already started.                                                                                    | `mcu_util.py -c -i /dev/ttyS1 -s`                                       |
| `-g`, `--version`              | Retrieve and display the combined hardware and firmware version information from the MCU.                                                                     | `mcu_util.py -c -i /dev/ttyS1 -g`                                       |
| `-r`, `--request-bootloader`   | Request that the MCU enters bootloader mode. (custom Klipper build required).                                    | `mcu_util.py -r -i /dev/ttyS1`                                          |
| `-b`, `--baud`                 | Set the serial baud rate for bootloader requests. The default baud rate is `230400`.                                                                          | `-b 230400`                                                           |

## Usage Examples

- **Initiate Handshake Only**  
  Initiate communication with the MCU by sending the handshake signal (0x75). Once the handshake is confirmed, no further handshake is required during that session.  
  ```bash
  mcu_util.py -c -i /dev/ttyS1
  ```

- **Retrieve Hardware and Firmware Version**  
  Check the combined hardware and firmware version available on the MCU.
  ```bash
  mcu_util.py -c -i /dev/ttyS1 -g
  ```

- **Flash Firmware**  
  Update the firmware after ensuring the MCU has been properly power cycled or the update command is placed in the initialization routine.
  ```bash
  mcu_util.py -c -i /dev/ttyS1 -u -f /usr/data/klipper/fw/K1/bed_klipper.bin
  ```

- **Start Firmware Application**  
  If the firmware application hasn't started yet, use this command to trigger the startup process.
  ```bash
  mcu_util.py -c -i /dev/ttyS1 -s
  ```

- **Bootloader Request Feature**  
    The `-r` or `--request-bootloader` option allows you to request that the MCU enters bootloader mode. This feature is     useful for initiating the bootloader without needing to restart the printer.

    **Important Note:** 
    This option is only supported in a special build of Klipper available at https://github.com/Fiddl3/klipper-creality-k1.

    To use this feature:
    1. Specify the serial port with the `-i` flag.
    2. Optionally set a custom baud rate using the `-b` flag (default is 230400).
        ```bash
        mcu_util.py -r -i /dev/ttyS1 -b 230400
        ```



## Detailed Workflow Explanation

1. **Handshake**:  
   The tool initiates communication by sending a handshake byte (`0x75`) to the MCU. The bootloader will await this acknowledgment (also `0x75`) within 15 seconds of power-up.

2. **Version Retrieval**:  
   A version request is sent (using the bytes `0x00` and `0xff`). The MCU responds with a 25-byte string (plus a CRC validation byte) that combines both hardware and firmware version details.

3. **Firmware Update Process**:  
   - **Sector Size Request**: Retrieves the sector size, which is used as a multiplier for dividing the firmware into correctly sized chunks.
   - **Update Request**: Sends a request (byte `0x01` followed by `0xfe`) to initiate the flashing sequence, followed by the firmware file size and its corresponding CRC.
   - **Firmware Transfer**: The firmware is transmitted in chunks (each validated with a CRC) until the entire file is successfully flashed to the device.

4. **Application Start**:  
   A startup command (using the bytes `0x02` and `0xfd`) is sent to initiate the newly flashed firmware. The MCU validates this command via CRC before starting the application.

5. **Bootloader Request**:  
   This feature is useful for initiating the bootloader without needing to restart the printer, the `-r` option requests that the MCU enters bootloader mode. Once the request is acknowledged, the script confirms the mode entry by re-initiating a handshake and version check.

## License and Disclaimer

This utility is provided under its applicable license. Use this tool at your own risk; the author is not liable for any damage or data loss due to improper use.

## Contact and Support

For additional information, troubleshooting, or contributions, please refer to the project repository or contact the maintainer.

---
