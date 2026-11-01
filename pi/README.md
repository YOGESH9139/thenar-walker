# Thenar Walker on a Raspberry Pi

`thenar_pi` is the Python port of `firmware/thenar_phone`: the same phone page, the same WebSocket protocol on port 81,
the same safety rules (300 ms link timeout, STOP latch, limp start, slew limits, calibrated safe ends), the same
calibrator line protocol (now over Wi-Fi on port 82), and the same calibration record (layout and CRC checked against
`tw_armcal.h` by a test). New: `GET /snap.jpg` gives the brain (Hasami: SAM + Muse) a camera frame, and the brain
drives through its own WebSocket on **port 83** with the phone's messages at lower priority: real phone input takes
control for 2 s (`E manual`), a phone STOP pauses the brain until a human sends `R` (`E paused`), the brain can always
STOP, and each side has its own 300 ms link timeout. With no brain connected the robot behaves exactly as before.

The ESP32 build stays in `firmware/` and still works. The Pi defaults to `THENAR_GRIPPER=parallel` for the
[Robonine rack-and-pinion gripper](https://github.com/roboninecom/SO-ARM100-101-102-Parallel-Gripper/blob/main/docs/specifications.md):
J6 is jaw gap in mm (0 = closed), capped at 14 mm/s. Set `THENAR_GRIPPER=rotary` for the old claw.
The `C{json}` message reports `gripper` and each joint's `units`. The calibration bytes/CRC are unchanged,
but records for one kind are invalid for the other and must not be reused.

## Wiring (BCM numbers; full table in [docs/WIRING_PI.md](../docs/WIRING_PI.md))
| Signal | Pi pin | Goes to |
|---|---|---|
| I2C SDA / SCL | GPIO2 (pin 3) / GPIO3 (pin 5) | PCA9685 SDA / SCL (and the optional ADS1115) |
| PCA9685 OE | GPIO17 (pin 11) | OE (active low: HIGH = servos off) |
| MDD10A PWM1 / PWM2 | GPIO12 (pin 32) / GPIO13 (pin 33) | hardware PWM 0 / 1, 20 kHz |
| MDD10A DIR1 / DIR2 | GPIO5 (pin 29) / GPIO6 (pin 31) | direction |
| Status LED | GPIO27 (pin 13) | LED + 330 Ω to GND (lit = phone linked, blinking = waiting) |
| GND | any GND pin | PCA9685 GND, MDD10A GND, buck GND (common ground) |

The Pi gets its **own 5 V 5 A buck** (a Pi 5 needs 5 A for full USB power); the servos keep their own 6 V supply via a
rated distribution block, with PCA9685 V+/GND as voltage reference. Never run six-servo current through the PCA9685
terminal or power servos from the Pi's 5 V pin: a stalled 25 kg·cm servo can brown out the Pi.
Battery voltage needs an ADC (the Pi has none): an ADS1115 on I2C (0x48, AIN0 through the same 100k/27k divider) is
optional; without it the page shows `-- V`.

## Set up the Pi (Raspberry Pi OS Bookworm 64-bit)
```
sudo raspi-config nonint do_i2c 0                       # I2C on
echo "dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4" | sudo tee -a /boot/firmware/config.txt
sudo reboot
sudo git clone https://github.com/nickthelegend/thenar-walker /opt/thenar-walker
cd /opt/thenar-walker/pi
sudo python3 -m venv --system-site-packages .venv      # system site-packages: Picamera2 comes from apt
sudo .venv/bin/pip install -e ".[pi]"
sudo i2cdetect -y 1                                     # expect 40 (PCA9685), 70 (all-call), and 48 if an ADS1115 is fitted
```

Calibration: the old MG996R numbers are **rotary only**; `seed-known` refuses them with the default parallel setting.
Measure all six installed servos with the calibrator: open `http://<robot>/calibrator`, press **Connect Pi (Wi-Fi)**.
For J6 measure the gap between the inner jaw faces with calipers at 20 and 60 mm, then set safe pulse ends with empty
jaws. Its slope should be 15–60 µs/mm; the 180° or 270° servo variant determines reachable stroke. `python -m
thenar_pi.armcal show` prints the record. The PWM servo has no torque limit or feedback: grip an item by commanding
measured item width minus a small squeeze, never fully closed. This physical setup is untested on the built robot.
Without a valid record no joint can be switched on.

## Run
```
sudo .venv/bin/python -m thenar_pi            # by hand; Ctrl+C = wheels 0, every servo limp
sudo cp systemd/thenar-pi.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now thenar-pi
journalctl -u thenar-pi -f                     # the same log lines as the ESP32's serial monitor
sudo python3 tools/setup_ap.py "Thenar Walker" # robot Wi-Fi ThenarWalker_TF, WPA2, phone opens http://192.168.4.1
```
`/etc/thenar-pi.env` (optional, not in git) can set `THENAR_SSID=ThenarWalker_TF`, `THENAR_CAMERA=0|off`, `THENAR_GRIPPER=parallel|rotary`, or any pin
(`THENAR_OE_PIN=17`, ...).

First time on the real robot: **wheels off the ground**, then check each wheel turns the right way with the phone
stick. If a side runs backwards, swap its motor leads (or flip `SIDE_SIGN` in `thenar_pi/config.py`).

## Without the robot
```
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m thenar_pi --dry-run       # page + protocol on :80/:81/:82/:83, no I2C, GPIO or camera
cd tests && ../.venv/bin/python -m pytest -q  # 38 tests collected (on Windows: .venv\Scripts\python -m pytest -q)
```
The tests drive the real robot logic, server and sockets on top of recording stand-ins for the I2C bus and the pins
(`tests/fakes.py`), and compile `tw_armcal.h` to prove the calibration record matches the ESP32's byte for byte.

## What is not tested yet
Everything that needs the real board: the PCA9685 on the Pi's I2C, the hardware PWM overlay on the actual Pi model,
gpiozero on the actual Pi, the MDD10A, the camera, and the access point. These are open items in CLAUDE.md.
