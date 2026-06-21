# About

`rpi_status_gpio.py` controls an LED (PWM) and a button on a Raspberry Pi.

**Normal mode**: the LED stays dim and flashes once every 2 seconds.

**Button hold**: if you hold the button for **5 seconds**, it runs `sudo shutdown -h now`.

# Run

```bash
sudo python3 rpi_status_gpio.py
```
