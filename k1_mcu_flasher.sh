#!/bin/bash

# K1 MCU Flasher Management Script

GR='\033[0;92m'
NC='\033[0m'

CONFIG_FILE="/etc/mcu_flasher.conf"
SERVICE_FILE="/etc/systemd/system/mcu_flasher.service"
WRAPPER_SCRIPT="/usr/local/bin/mcu_flasher_wrapper.sh"
LOG_FILE="/var/log/mcu_flasher.log"
MCU_UTIL_DEST="/usr/local/bin/mcu_util.py"
BUILD_DIR="/tmp/klipper_build"
KLIPPER_REPO="https://github.com/Fiddl3/klipper-creality-k1"
KLIPPER_CONFIG=(
    "CONFIG_LOW_LEVEL_OPTIONS=y"
    "CONFIG_MACH_GD32=y"
    "CONFIG_STM32_FLASH_START_3000=y"
    "CONFIG_STM32_SERIAL_USART2=y"
    "CONFIG_SERIAL_BAUD=230400"
)

detect_ports() {
    echo "Available COM ports:"
    ls /dev/ttyS* /dev/ttyUSB* /dev/ttyA* 2>/dev/null | cat -n | sed 's/^ *\([0-9]*\)/ \1)/'
}

check_existing_installation() {
    [[ -f "$SERVICE_FILE" || -f "$WRAPPER_SCRIPT" || -f "$CONFIG_FILE" ]]
}

handle_existing_installation() {
    echo "MCU Flasher service is already installed:"
    [ -f "$SERVICE_FILE" ] && echo " - Service file: $SERVICE_FILE"
    [ -f "$WRAPPER_SCRIPT" ] && echo " - Wrapper script: $WRAPPER_SCRIPT"
    [ -f "$CONFIG_FILE" ] && echo " - Config file: $CONFIG_FILE"
    while true; do
        read -p "Choose action: [R]einstall/[A]bort (default: A): " choice
        case "${choice,,}" in
            r|reinstall)
                echo "Uninstalling existing service..."
                uninstall_service
                if check_existing_installation; then
                    echo "Error: Failed to remove existing installation!" >&2
                    exit 1
                fi
                return 0
                ;;
            a|abort|"")
                echo "Installation aborted"
                exit 0
                ;;
            *)
                echo "Invalid choice, please try again"
                ;;
        esac
    done
}

install_service() {
    (( EUID != 0 )) && echo "Run with sudo" && exit 1
    if check_existing_installation; then
        handle_existing_installation
    fi
    
    SCRIPT_DIR=$(dirname "$(realpath "$0")")
    if [ ! -f "$SCRIPT_DIR/mcu_util.py" ]; then
        echo "Error: mcu_util.py not found in $SCRIPT_DIR" >&2
        exit 1
    fi
    if ! cp -v "$SCRIPT_DIR/mcu_util.py" "$MCU_UTIL_DEST"; then
        echo "File copy failed!" >&2
        exit 1
    fi
    chmod +x "$MCU_UTIL_DEST"
    
    mkdir -p $(dirname $CONFIG_FILE)
    echo -e "# MCU Flasher Configuration\nMODE=normal" > $CONFIG_FILE
    detect_ports
    read -p "Enter port number from list or full path: " port_input
    if [[ $port_input =~ ^[0-9]+$ ]]; then
        PORT=$(ls /dev/ttyS* /dev/ttyUSB* /dev/ttyA* 2>/dev/null | sed -n ${port_input}p)
    else
        PORT=$port_input
    fi
    [[ ! -e "$PORT" ]] && echo "Error: Invalid port" && exit 1
    sed -i "/^MCU_PORT/d" $CONFIG_FILE
    echo "MCU_PORT=$PORT" >> $CONFIG_FILE
    
    cat > $WRAPPER_SCRIPT << EOL
#!/bin/bash
source $CONFIG_FILE
$MCU_UTIL_DEST -i \$MCU_PORT -\$MODE \$FLASH_FILE >> $LOG_FILE 2>&1
EOL
    chmod +x $WRAPPER_SCRIPT
    
    cat > $SERVICE_FILE << EOL
[Unit]
Description=MCU Flasher Service
After=network.target

[Service]
ExecStart=$WRAPPER_SCRIPT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL
    
    if ! systemctl enable mcu_flasher; then
        echo "Failed to enable service!" >&2
        uninstall_service
        exit 1
    fi
    echo "Service installed successfully"
}

uninstall_service() {
    systemctl stop mcu_flasher
    systemctl disable mcu_flasher
    rm -f $SERVICE_FILE $CONFIG_FILE $WRAPPER_SCRIPT "$MCU_UTIL_DEST"
    echo "Service uninstalled"
}

flash_mode() {
    [[ -z "$1" ]] && echo "Specify firmware path" && exit 1
    local abs_path
    abs_path=$(realpath -e "$1" 2>/dev/null || echo "$1")
    if [ ! -f "$abs_path" ]; then
        echo "File not found: $1 (absolute path: $abs_path)" >&2
        exit 1
    fi
    [[ "$abs_path" != "$1" ]] && echo "Converted path: $1 → $abs_path"
    local version=$(dd if="$abs_path" bs=1 skip=$((0x200)) count=16 2>/dev/null | tr -d '\0')
    
    echo -e "Select flash mode: binary file version → ${GR}$version${NC}"
    echo -e " 1)\tBootloader mode (direct upload)"
    echo -e " 2)\tService mode (default, requires reboot)"
    read -p "Choose mode (C to cancel): " flash_choice
    echo
    [[ ! $flash_choice =~ ^[12]$ ]] && echo "Aborted" && exit 0
    case $flash_choice in
        1)
            detect_ports
            read -p "Enter COM port for bootloader: " port_input
            if [[ $port_input =~ ^[0-9]+$ ]]; then
                port=$(ls /dev/ttyS* /dev/ttyUSB* /dev/ttyA* 2>/dev/null | sed -n ${port_input}p)
            else
                port=$port_input
            fi
            read -p "Enter baudrate (default 230400): " baudrate
            baudrate=${baudrate:-230400}
            
            if systemctl is-active --quiet klipper; then
                read -p "Klipper is running. Stop it now? (y/n) "
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    systemctl stop klipper
                    sleep 2
                    if systemctl is-active --quiet klipper; then
                        echo "Failed to stop Klipper!" >&2
                        exit 1
                    fi
                else
                    echo "Flash aborted" >&2
                    exit 1
                fi
            fi
            
            echo
            echo "======================= Entering bootloader mode ======================="
            echo "Entering bootloader mode..."
            /usr/bin/python3 ./mcu_util.py -i $port -b $baudrate -r
            mcu_exit=$?
            if [ $mcu_exit -eq 0 ]; then
                echo "Failed to enter bootloader mode!" >&2
                exit 1
            fi
            echo
            echo "======================= Starting firmware update ======================="
            /usr/bin/python3 ./mcu_util.py -i $port -u -f "$1"
            mcu_exit=$?
            if [ $mcu_exit -eq 0 ]; then
                echo "Flashing failed!" >&2
                exit 1
            fi
            echo "=========================== Flash successful ==========================="
            echo
            read -p "Flash successful. Restart Klipper? (y/n) " -n 1 -r
            echo
            [[ $REPLY =~ ^[Yy]$ ]] && systemctl start klipper
            ;;
        2)
            sed -i "/^FLASH_FILE/d" $CONFIG_FILE
            echo "FLASH_FILE=$abs_path" >> $CONFIG_FILE
            sed -i 's/^MODE=.*/MODE=flash/' $CONFIG_FILE
            echo
            echo "================================================"
            echo "System will shut down in 5 seconds... "
            echo "IMPORTANT: After shutdown, please disconnect"
            echo "and reconnect the power to complete the process."
            echo "================================================"
            sleep 5
            sudo shutdown -h now
            ;;
        *)
            echo "Invalid mode selected!" >&2
            exit 1
            ;;
    esac
}

select_mcu() {
    echo "Select the GD32 microcontroller variant:"
    echo " 1) GD32F303XB"
    echo " 2) GD32F303XC"
    echo " 3) GD32F303XE"
    echo " 4) GD32F303XG"
    echo " 5) GD32F303XI"
    echo " 6) GD32F303XK"
    echo " 7) Manual configuration (make menuconfig)"
    read -p "Choose a number (1-7): " mcu_choice
    case $mcu_choice in
        1) MCU="GD32F303XB" ;;
        2) MCU="GD32F303XC" ;;
        3) MCU="GD32F303XE" ;;
        4) MCU="GD32F303XG" ;;
        5) MCU="GD32F303XI" ;;
        6) MCU="GD32F303XK" ;;
        7) MCU="MANUAL" ;;
        *) echo "Invalid choice. Defaulting to GD32F303XB."; MCU="GD32F303XB" ;;
    esac
    echo "Selected: $MCU"
}

build_klipper() {
    local SCRIPT_DIR
    SCRIPT_DIR=$(dirname "$(realpath "$0")")
    if ! command -v git >/dev/null || ! command -v make >/dev/null; then
        echo "Install required packages:"
        echo "sudo apt install git build-essential libncurses-dev"
        exit 1
    fi
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR" || exit 1
    if ! git clone "$KLIPPER_REPO" .; then
        echo "Failed to clone repository!" >&2
        exit 1
    fi
    select_mcu
    if [ "$MCU" != "MANUAL" ]; then
        echo "Applying predefined configuration for $MCU"
        KLIPPER_CONFIG+=("CONFIG_MACH_${MCU}=y")
        printf "%s\n" "${KLIPPER_CONFIG[@]}" > .config
        make olddefconfig
    else
        echo "Running manual configuration..."
        printf "%s\n" "${KLIPPER_CONFIG[@]}" > .config
        make olddefconfig
        make menuconfig
    fi
    if ! grep -q "CONFIG_MACH_GD32=y" .config; then
        echo "Error: GD32 not selected in configuration!" >&2
        exit 1
    fi
    if ! make -j$(nproc); then
        echo "Compilation failed!" >&2
        cd - >/dev/null
        rm -rf "$BUILD_DIR"
        exit 1
    fi
    local bin_file="$BUILD_DIR/out/klipper.bin"
    if [ -f "$bin_file" ]; then
        cp -v "$bin_file" "$SCRIPT_DIR/"
        echo "Copied klipper.bin to script directory: $SCRIPT_DIR"
    else
        echo "Output file not found!" >&2
        cd - >/dev/null
        rm -rf "$BUILD_DIR"
        exit 1
    fi
    rm -rf "$BUILD_DIR"
    echo "Build directory cleaned: $BUILD_DIR"
    cd $SCRIPT_DIR
    read -p "Flash firmware now? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || return 0
    if ! $0 --flash "$SCRIPT_DIR/klipper.bin"; then
        echo "Flashing failed!" >&2
        exit 1
    fi
}

verify_installation() {
    echo "Verifying installation..."
    local success=0
    [ -f "$MCU_UTIL_DEST" ] && echo "mcu_util.py: OK" || { echo "mcu_util.py: MISSING"; success=1; }
    [ -f "$CONFIG_FILE" ] && echo "Config file: OK" || { echo "Config file: MISSING"; success=1; }
    [ -f "$SERVICE_FILE" ] && echo "Service file: OK" || { echo "Service file: MISSING"; success=1; }
    [ -f "$WRAPPER_SCRIPT" ] && echo "Wrapper script: OK" || { echo "Wrapper script: MISSING"; success=1; }
    return $success
}

bootloader_mode() {
    sed -i 's/^MODE=.*/MODE=bootloader/' $CONFIG_FILE
    echo "System will shut down in 5 seconds to enter bootloader mode..."
    echo "IMPORTANT: After shutdown, please disconnect and reconnect the power to enter bootloader mode."
    sleep 5
    sudo shutdown -h now
}

view_log() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "Log file not found: $LOG_FILE"
        exit 1
    fi
    echo "Displaying last 50 lines of log file. Press Ctrl+C to exit."
    echo "----------------------------------------"
    tail -n 50 -f "$LOG_FILE"
}

show_help() {
    echo "Usage: $0 [OPTION]"
    echo "K1 MCU Flasher Management Script"
    echo
    echo "Options:"
    echo "  --install       Install the MCU Flasher service"
    echo "  --uninstall     Uninstall the MCU Flasher service"
    echo "  --bootloader    Enter bootloader mode"
    echo "  --flash FILE    Flash firmware file"
    echo "  --build-klipper Build Klipper firmware"
    echo "  --view-log      View MCU Flasher log"
    echo "  --help          Display this help message"
    echo
    echo "Example:"
    echo "  $0 --flash /path/to/firmware.bin"
}

case $1 in
    "--install")
        install_service
        ;;
    "--uninstall")
        uninstall_service
        ;;
    "--bootloader")
        bootloader_mode
        ;;
    "--flash")
        flash_mode "$2"
        ;;
    "--build-klipper")
        build_klipper
        ;;
    "--view-log")
        view_log
        ;;
    "--help")
        show_help
        ;;
    *)
        show_help
        exit
esac        