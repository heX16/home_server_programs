
### Как узнать, что доступен TRIM/discard

Есть два практичных способа.

#### 1) На уровне блочного устройства (то, что видит Linux)

```bash
lsblk -D -o NAME,DISC-GRAN,DISC-MAX,DISC-ZERO /dev/sdb
```

- Если **`DISC-GRAN`** и **`DISC-MAX`** **не 0**, значит discard поддерживается и пробрасывается до устройства.

Дополнительно (sysfs):

```bash
cat /sys/block/sdb/queue/discard_granularity
cat /sys/block/sdb/queue/discard_max_bytes
```

- Если значения **не 0** — discard включён на уровне очереди I/O.

#### 2) На уровне самого SSD (ATA фича TRIM)

Для твоего диска через USB‑мост:

```bash
sudo smartctl -i -d sat /dev/sdb | grep -i trim
```

Должно показать что-то вроде `TRIM Command: Available ...`.


### Как получить нужные поля

```bash
sudo smartctl -l devstat -d sat /dev/sdb
```

Только нужные строки одной командой:

```bash
sudo smartctl -l devstat -d sat /dev/sdb | grep -E "Lifetime Power-On Resets|Power-on Hours|Percentage Used Endurance Indicator|Logical Sectors Written|Logical Sectors Read|Number of Write Commands|Number of Read Commands"
```

Что есть что:

- **Resets**: `Lifetime Power-On Resets`
- **Hours**: `Power-on Hours`
- **Percentage Used**: `Percentage Used Endurance Indicator`
- **Объём записи/чтения**: `Logical Sectors Written` / `Logical Sectors Read`
- **Кол-во команд**: `Number of Write Commands` / `Number of Read Commands`

