
from machine import Pin, ADC, SoftI2C, Timer, RTC
from mqtt import MQTTClient 
import time
import ssd1306
import webrepl
import ntptime
import network
import ubinascii

# Wifi object
wlan = network.WLAN(network.STA_IF)

# MQTT
client_id = ubinascii.hexlify(machine.unique_id())
topic_sub = b'home/%s/cmd' % (dev_name)
topic_pub = b'home/%s/metrics' % (dev_name)

# Pin and metric variables
led = Pin(2,Pin.OUT)
motionPin = 34
pir = Pin(motionPin, Pin.IN)
motion = False
pin_value = 0
signal = 0
count = 0
message_interval = 300
signal_interval = 30

# setup I2C
i2c = SoftI2C(sda=Pin(21), scl=Pin(22))
display = ssd1306.SSD1306_I2C(128, 64, i2c)
display.contrast(50)

# y_log_offsets for each row of text (scrolling text log)
y_log_offsets = [14, 24, 34, 44, 54]

# initialize logs for display
logs = []
i = 0
while i < len(y_log_offsets):
    logs.append('')
    i += 1

def wifi_connect(wifi_ssid,wifi_passwd):
  wlan.active(True)
  if not wlan.isconnected():
    print('\nConnecting to network', end='')
    wlan.connect(wifi_ssid, wifi_passwd)
    while not wlan.isconnected():
      print('.', end='')
      time.sleep(0.5)
      pass
  print()
  print("Interface's MAC: ", ubinascii.hexlify(network.WLAN().config('mac'),':').decode()) # print the interface's MAC
  print("Interface's IP/netmask/gw/DNS: ", wlan.ifconfig(),"\n") # print the interface's IP/netmask/gw/DNS addresses

def setup_ntp():
  print("Local time before synchronization：%s" %str(time.localtime()))
  ntptime.host = ntp_server
  ntptime.settime()
  print("Local time after synchronization：%s" %str(time.localtime()))
  (year, month, mday, week_of_year, hour, minute, second, milisecond)=RTC().datetime()
  hour = hour + hour_adjust
  RTC().init((year, month, mday, week_of_year, hour, minute, second, milisecond)) # GMT correction. GMT-7
  print("Local time after timezone offset: %s" %str(time.localtime()))
  print("{}/{:02d}/{:02d} {:02d}:{:02d}:{:02d}".format(RTC().datetime()[0], RTC().datetime()[1], RTC().datetime()[2], RTC().datetime()[4], RTC().datetime()[5],RTC().datetime()[6]))

def sub_cb(topic, msg):
  # print((topic, msg))
  last_receive = time.time()
  print('%s: received message on topic %s with msg: %s' % (last_receive, topic, msg))
  if topic == topic_sub and msg == b'ping':
    client.publish(topic_pub, b'pong')
    print('sent pong')

def connect_and_subscribe():
  global client_id, mqtt_server, topic_sub
  client = MQTTClient(client_id, mqtt_server, port=1883, user=mqtt_user, password=mqtt_password)
  client.set_callback(sub_cb)
  client.connect()
  client.subscribe(topic_sub)
  print('Connected to %s MQTT broker, subscribed to %s topic' % (mqtt_server, topic_sub))
  return client

def restart_and_reconnect():
  print('Failed to connect to MQTT broker. Reconnecting...')
  time.sleep(10)
  machine.reset()

def blink():
    led.on()
    time.sleep_ms(500)
    led.off()
    time.sleep_ms(500)

def draw_status(status, update=True):
  display.fill_rect(0, 0, 128, 12, 0) #  draw a solid rectangle x,y for +x,+y, color=1
  display.rect(0, 0, 128, 12, 1)
  # print(str(pin_value))
  display.text(status, 2, 2, 1)
  if update:
    display.show()  # update display

def draw_log(msg):
  global logs
  display.fill(0)  # clear display by filling with black
  logs = logs[1:]  # remove first element by starting at index 1 (removes index 0)
  logs.append(msg)  # add log entry to end of list
  # write display buffer with logs
  for i, y in enumerate(y_log_offsets):
    display.text(str(logs[i]), 0, y, 1)
  status = 's={0}, v={1}'.format(signal, pin_value)
  draw_status(status)
  # display.show()  # update display

def handle_interrupt(pin):
  global motion
  print('handler triggered')
  motion = True

def wait_for_sensor():
  status = 's={0}, {1}'.format(signal, 'sleep 60')
  draw_status(status)
  print('wait 60 seconds for sensor to stabilize')
  time.sleep(60)

def loop():

  global pin_value
  global count
  global motion
  global signal

  last_message = 0
  last_signal = 0
  TimeFormat = '{0:02d}:{1:02d}'

  while True:
    try:
      client.check_msg()

      # print pin value for troubleshooting
      pin_value = pir.value()
      time_check = time.time()

      if motion:
        count += 1
        signal = wlan.status('rssi')
        last_signal = time_check
        msg = b'{{"s":"{0}","m":"1"}}'.format(signal)
        blink()
        client.publish(topic_pub, msg)
        last_message = time_check
        year, month, day, hour, mins, secs, weekday, yearday = time.localtime() 
        timestamp = TimeFormat.format(hour, mins)
        print('%s: published trigger event %d' % (timestamp, count))
        draw_log('{0} {1}'.format(timestamp, count))
        motion = False
      
      elif (time_check - last_message) > message_interval:
        signal = wlan.status('rssi')
        last_signal = time_check
        msg = b'{{"s":"{0}","m":"0"}}'.format(signal)
        client.publish(topic_pub, msg)
        last_message = time_check
        year, month, day, hour, mins, secs, weekday, yearday = time.localtime() 
        timestamp = TimeFormat.format(hour, mins)
        print('%s: published status: signal=%s' % (timestamp, signal))
        status = 's={0}, v={1}'.format(signal, pin_value)
        draw_status(status)

      elif (time_check - last_signal) > signal_interval:
        signal = wlan.status('rssi')
        last_signal = time_check
        status = 's={0}, v={1}'.format(signal, pin_value)
        draw_status(status)

      time.sleep(1)
    except OSError as e:
      # If anything fails, restart and reconnect
      print('err: {0}, restart and reconnect'.format(e))
      restart_and_reconnect()

# This is used to print the temperature.  It is likely only needed if troubleshooting heat issues.
# import esp32  # this is only used for internal temperature check (only use )
# print('Temperature (F): {0}'.format(esp32.raw_temperature()))

wifi_connect(ssid, password)
# Setup the button input pin with a pull-up resistor.
pir.irq(trigger=Pin.IRQ_RISING, handler=handle_interrupt)
print('Setup interrupt handler complete')
signal = wlan.status('rssi')
webrepl.start()
setup_ntp()

# Connect to MQTT
try:
  client = connect_and_subscribe()
except OSError as e:
  restart_and_reconnect()

# check if the device woke from a deep sleep
boot_reason = machine.reset_cause()
if boot_reason == machine.DEEPSLEEP_RESET:
  print('woke from a deep sleep')  # constant = 4
  # no need to wait for sensor, but different logic/flow needed for deep sleep
elif boot_reason == machine.SOFT_RESET:
  print('soft reset detected')  # constant = 5
  # no need to wait for sensor
elif boot_reason == machine.PWRON_RESET:
  print('power on detected') # constant = 1
  wait_for_sensor()
elif boot_reason == machine.WDT_RESET:
  print('WDT_RESET detected') # constant = 3
  wait_for_sensor()
else:
  print('boot_reason={0}'.format(boot_reason))

# When not using deep-sleep, loop forever
loop()

