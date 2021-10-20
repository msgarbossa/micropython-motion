# micropython-motion

This project uses MicroPython to detect motion and send MQTT messages for events and status updates.  An OLED screen is used for current status and displaying the time of the last 5 events.  NTP is used to get the time.  Since I'm new to MicroPython, additional information is provided below.

Basic steps:

1. Copy boot.py.sample to boot.py and update with WiFi, MQTT, and NTP settings.
2. [Set WebREPL password](#webrepl).
3. Push all Python files using [ampy](#ampy) (assumes MicroPython already [flashed](#flash-micropython)).

## Diagram

![wiring diagram](/img/esp32_motion_sensor_oled.png)

As detailed below, I experienced continuous false positive events without the resistor.

## PIR sensor

This page best describes how to adjust the HC-SR501 board:

https://lastminuteengineers.com/pir-sensor-arduino-tutorial/

The HC-SR501 and some of the variations can be problematic and trigger many false positives.  Most threads say it's caused by noise on the GPIO ports, WiFi on the microcontroller, or power supply issues.  Providing a minimum of 5V seems mandatory.  Putting a separate 10K pull down resistor on the GPIO input made the biggest difference in my experience.  With very rare false positives, any additional tuning could be done in software to sample multiple events.

## Flash MicroPython

https://micropython.org/download/esp32/

Use firmware built with ESP-IDF v4.x

```bash
esptool.py --port /dev/ttyUSB0 erase_flash
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x1000 ~/Downloads/esp32-20210902-v1.17.bin
```

## ampy

Make sure user is in the dialout group to have write permissions to the /dev/ttyUSB0 device.


Install Python modules for ampy (can use Python virtualenv or install globally since it shouldn't conflict with anything else)

```bash
pip3 install adafruit-ampy
pip3 install rshell
```

```bash
ampy --port /dev/ttyUSB0 --baud 115200 put boot.py
ampy --port /dev/ttyUSB0 --baud 115200 put main.py
ampy --port /dev/ttyUSB0 --baud 115200 put ssd1306.py
```

## screen

The screen command is used to connect to the serial port.  It's important to know that you cannot upload with ampy while attached to the serial port with screen so this process gets pretty repetitive.  WebREPL might work around some of this, but it seems a little more clunky than mastering these steps.

```bash
sudo apt-get install -y screen
```

### Attach to USB port

```bash
screen /dev/ttyUSB0 115200
```

After attaching to USB port, press "Enter" to get Python shell (see [Python shell help](#python-shell-help) below).

Once in the screen session and in the python shell (not screen command), press Ctrl-D to soft-reboot after uploading a file.  You cannot upload a file with ampy if screen is also attached via the serial port.

### Exit screen (kill screen).

This command kills the screen session to free up the serial port.

The Ctrl-a is the default escape key to send the command to screen (not for Python shell).
```
Ctrl-a, k
```

## Python shell help

```
>>> help()
Welcome to MicroPython on the ESP32!

For generic online docs please visit http://docs.micropython.org/

For access to the hardware use the 'machine' module:

import machine
pin12 = machine.Pin(12, machine.Pin.OUT)
pin12.value(1)
pin13 = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)
print(pin13.value())
i2c = machine.I2C(scl=machine.Pin(21), sda=machine.Pin(22))
i2c.scan()
i2c.writeto(addr, b'1234')
i2c.readfrom(addr, 4)

Basic WiFi configuration:

import network
sta_if = network.WLAN(network.STA_IF); sta_if.active(True)
sta_if.scan()                             # Scan for available access points
sta_if.connect("<AP_name>", "<password>") # Connect to an AP
sta_if.isconnected()                      # Check for successful connection

Control commands:
  CTRL-A        -- on a blank line, enter raw REPL mode
  CTRL-B        -- on a blank line, enter normal REPL mode
  CTRL-C        -- interrupt a running program
  CTRL-D        -- on a blank line, do a soft reset of the board
  CTRL-E        -- on a blank line, enter paste mode

For further help on a specific object, type help(obj)
For a list of available modules, type help('modules')
>>> 
```

## WebREPL

webrepl is not enabled by default.  Most online documentation says to run import webrepl from a REPL shell and follow the prompts.  It seems to work better this way.  WebREPL is great for remotely managing a MicroPython controller connected to the network without the need for a serial port connection.

```
echo "PASS = 'password'" > webrepl_cfg.py
ampy --port /dev/ttyUSB0 --baud 115200 put webrepl_cfg.py
```

At the top of main.py with other import statements:

```
import webrepl
```

Add the following to main.py after a place where `print(station.ifconfig())` runs successfully:

```
webrepl.start()
```

The client tool is hosted at http://micropython.org/webrepl/.  It runs locally from the browser.

It's recommended to make a DHCP reservation for the MAC/IP so the IP address can be consistently used for remote connections.

## Install mqtt library in project

```bash
wget https://raw.githubusercontent.com/pycom/pycom-libraries/master/examples/mqtt/mqtt.py
ampy --port /dev/ttyUSB0 --baud 115200 put mqtt.py
```

## Install ssd1306 OLED library in project

```bash
wget https://raw.githubusercontent.com/micropython/micropython/master/drivers/display/ssd1306.py
ampy --port /dev/ttyUSB0 --baud 115200 put ssd1306.py
```

## Deep Sleep


### Save variable to flash

Flash memory has limited write cycles around 10,000.  RTC memory a dictionary of 64 key/value pairs. The dictionary keys are integers 0-63.  There is also one RTC variable for storing a string.  There isn't a lot of documentation on this.

```
import machine
import ujson
rtc = machine.RTC()
d = {1:'one', 2:'two'}  # Example data to save
rtc.memory(ujson.dumps(d))  # Save in RTC RAM

r = ujson.loads(rtc.memory())  # Restore from RTC RAM
# r == {2: 'two', 1: 'one'}
```
