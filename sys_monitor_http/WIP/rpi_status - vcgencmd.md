# Raspberry Pi 4 B

## Temperature
`vcgencmd measure_temp`

> `temp=57.4'C` 

## Throttled (power / thermal status)
`vcgencmd get_throttled`

Returns a hexadecimal value (32-bit). Meaning of bits:

### Current state (bits 0–3)

| Bit | Hex mask | Meaning |
|-----|----------|---------|
| 0   | `0x1`    | Under-voltage detected |
| 1   | `0x2`    | Arm frequency capped |
| 2   | `0x4`    | Currently throttled |
| 3   | `0x8`    | Soft temperature limit active |

### Historical state since last boot (bits 16–19)

| Bit | Hex mask | Meaning |
|-----|----------|---------|
| 16  | `0x10000` | Under-voltage has occurred |
| 17  | `0x20000` | Arm frequency capping has occurred |
| 18  | `0x40000` | Throttling has occurred |
| 19  | `0x80000` | Soft temperature limit has occurred |

### Examples

- `throttled=0x0` — no issues, current or historical.
- `0x50000` — bits 16 and 18 set: under-voltage and throttling occurred in the past (e.g. weak PSU at boot), not active now.
- `0x50005` — bits 0, 2, 16, 18: under-voltage and throttling **right now** and have occurred since boot.
- `0x80008` — bits 3 and 19: soft temperature limit active now and has occurred since boot.

### Practical meaning

- **Under-voltage (0, 16)** — power supply or cable insufficient; use a proper 5V 3A PSU (e.g. official Pi PSU).
- **Throttling / temperature (2, 3, 18, 19)** — overheating; improve cooling or reduce load.
- **Arm frequency capped (1, 17)** — CPU frequency was or is limited (often together with thermal or power limits).

**Source:** [Raspberry Pi OS — vcgencmd get_throttled](https://www.raspberrypi.com/documentation/computers/os.html#get_throttled)
