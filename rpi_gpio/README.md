# About

`rpi_status_gpio.py` controls an LED (PWM) and a button on a Raspberry Pi.

**Normal mode**: the LED stays dim and flashes once every 2 seconds.

**Button hold actions** are configured in `options`:

- `button_shutdown`: which `ButtonEvent` runs `sudo shutdown -h now` (`'RELEASED_HOLD_2S'`, `'HOLD_5S'`, or `'none'`)
- `button_reboot`: which `ButtonEvent` runs `sudo reboot` (`'RELEASED_HOLD_2S'`, `'HOLD_5S'`, or `'none'`)

Defaults: shutdown on `HOLD_5S` (hold 5 seconds while pressed), reboot disabled.

Examples:
- shutdown only (current default): `'button_shutdown': 'HOLD_5S'`, `'button_reboot': 'none'`
- reboot on 2–4s hold, shutdown on 5s: `'button_shutdown': 'HOLD_5S'`, `'button_reboot': 'RELEASED_HOLD_2S'`
- reboot only: `'button_shutdown': 'none'`, `'button_reboot': 'RELEASED_HOLD_2S'`

# Run

```bash
sudo python3 rpi_status_gpio.py
```
