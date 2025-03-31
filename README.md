# K1 MCU Flasher Management Script (beta)

## Overview

The **K1 MCU Flasher Management Script** is a tool designed to manage firmware flashing and service configuration for microcontrollers used in Creality K1 devices. It simplifies the process of installing, uninstalling, and flashing firmware while providing options for bootloader mode, Klipper firmware building, and log viewing.

This script is specifically intended for use with the **nozzle onboard MCU**. In **normal mode**, it enforces the startup of Klipper on the MCU, which can help speed up the printer's initialization process by ensuring that Klipper on the MCU is ready before the main Klipper service starts on the SBC (Single Board Computer).

---

## Features

- Install and uninstall the MCU flasher service.
- Flash firmware files directly or through service mode.
- Enter bootloader mode for manual flashing.
- Build Klipper firmware with predefined or manual configurations.
- View logs for troubleshooting.

---

## Requirements

- **Operating System**: Linux-based systems (e.g., Ubuntu, Debian).
- **Dependencies**:
  - `git`
  - `build-essential`
  - `libncurses-dev`
  - `python3`

---

## Installation

1. Clone the repository or download the script:
   ```bash
   git clone https://github.com/your-repo/k1-mcu-flasher.git
   cd k1-mcu-flasher
   ```

2. Run the script with appropriate options (see below).

---

## Usage

### Command Options

```bash
./k1_mcu_flasher.sh [OPTION]
```

| Option           | Description                                                                 |
|-------------------|-----------------------------------------------------------------------------|
| `--install`       | Install the MCU Flasher service.                                           |
| `--uninstall`     | Uninstall the MCU Flasher service.                                         |
| `--bootloader`    | Enter bootloader mode for manual flashing.                                 |
| `--flash FILE`    | Flash a specific firmware file.                                            |
| `--build-klipper` | Build Klipper firmware with predefined or manual configurations.           |
| `--view-log`      | View the last 50 lines of the MCU flasher log file.                        |
| `--help`          | Display help information about script usage.                               |

---

### Examples

#### Install the Service
To install the MCU Flasher service:
```bash
sudo ./k1_mcu_flasher.sh --install
```

This command will:
1. Check for existing installations and handle them if found.
2. Copy necessary files to system directories.
3. Create a configuration file and prompt you to select an MCU port.
4. Set up a systemd service that ensures Klipper starts on the nozzle onboard MCU before starting the main Klipper service on the SBC.
5. Enable the service to run on system startup.

This setup ensures that your printer initializes faster and more reliably by guaranteeing that Klipper on the MCU is ready before communication with the SBC begins.

---

#### Flash Firmware
To flash a specific firmware file:
```bash
sudo ./k1_mcu_flasher.sh --flash /path/to/firmware.bin
```

This command will:
1. Verify that the specified firmware file exists.
2. Extract and display the firmware version from the binary file.
3. Prompt you to choose between two flashing modes:
   - **Bootloader Mode**: Flash directly via a selected COM port.
   - **Service Mode**: Update configuration and reboot to flash automatically.

For **Bootloader Mode**:
- Detect available COM ports and prompt you to select one.
- Stop any running Klipper services to avoid conflicts.
- Enter bootloader mode, upload the firmware, and restart Klipper if desired.

For **Service Mode**:
- Save the firmware path in the configuration file.
- Shut down your system, after which you must disconnect and reconnect power to complete flashing.

---

#### Enter Bootloader Mode
To enter bootloader mode for manual flashing:
```bash
sudo ./k1_mcu_flasher.sh --bootloader
```

This command will:
1. Update the configuration file to set "bootloader" as the current mode.
2. Shut down your system safely.
3. Prompt you to disconnect and reconnect power to enter bootloader mode.

This is useful when performing manual operations or troubleshooting issues with your MCU.

---

#### Build Klipper Firmware
To build Klipper firmware:
```bash
sudo ./k1_mcu_flasher.sh --build-klipper
```

This command will:
1. Check if required tools (`git`, `make`) are installed.
2. Clone a custom Klipper repository from GitHub into a temporary build directory.
3. Prompt you to select your GD32 microcontroller variant or configure manually using `menuconfig`.
4. Compile Klipper firmware based on your selected configuration.
5. Copy the resulting `klipper.bin` file into your script directory for easy access.
6. Offer to flash this newly compiled firmware immediately.

This feature allows you to customize and build Klipper firmware tailored specifically for your device's hardware.

---

#### View Logs
To view recent logs from the MCU Flasher service:
```bash
sudo ./k1_mcu_flasher.sh --view-log
```

This command will:
1. Display the last 50 lines of logs from `/var/log/mcu_flasher.log`.
2. Continuously show new log entries in real-time (using `tail -f`).

This is helpful for debugging issues related to flashing or monitoring service activity.

---

#### Help Command
To display help information about available options:
```bash
./k1_mcu_flasher.sh --help
```

This command provides a summary of all available options, their descriptions, and usage examples.

---

## Notes

- Always run this script with superuser privileges (`sudo`) when performing installation or flashing operations.
- After entering bootloader mode or flashing in service mode, disconnect and reconnect power to complete initialization.
- The script automatically detects available COM ports during installation and bootloader operations, simplifying port selection.

---

## License

This script is open-source and distributed under the MIT License.

Feel free to modify it according to your needs!

---
```


# Instructions for mcu_tools.py

---
```



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
