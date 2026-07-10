# `gen_ha_config.py` — краткая документация

Скрипт генерирует набор YAML-файлов для Home Assistant из CSV со списком сигналов (DI/DO) и их MQTT-путей.

## Как запускать

- **Вход**: CSV-файл (`;`-разделитель, кодировка UTF‑8).
- **Выход**: папка с несколькими YAML-файлами.

Пример:

```bash
python gen_ha_config.py --csv="signals.csv" --out="out_ha"
```

## Что именно генерируется

В выходной директории создаются подпапки и файлы:

- **`mqtt/di.yaml`**
  - MQTT `binary_sensor` для всех строк CSV с `Тип = DI` (формат `mqtt:` list-per-item).
- **`mqtt/do.yaml`**
  - MQTT `switch` для всех строк CSV с `Тип = DO` (обычные DO, без `*_sys`).
- **`mqtt/do_sys.yaml`**
  - MQTT `switch` для системных дублей `*_sys` (см. раздел "Системные дубликаты DO").
- **`mqtt/extra.yaml`**
  - Пустой список (резерв под будущие типы/ручные добавления).
- **`customize/customize_gen.yaml`**
  - `homeassistant.customize`: выставляет `friendly_name` для каждого сгенерированного entity.
- **`lovelace/tab-*.yaml`**
  - Lovelace-дашборды (несколько файлов): для каждой уникальной непустой `Вкладка` генерируется отдельный YAML-файл
    с одним view «Комнаты» с карточками по комнатам (колонка `Группа`), внутри — только DO (`switch.*`).
- **`lovelace/debug-generated.yaml`**
  - Отдельный Lovelace-дашборд для отладки: два view — **DI** (`binary_sensor.*`) и **Sys DO** (`switch.*_sys`),
    карточки сгруппированы по ящику (`Box<Я.>`), у каждой сущности иконка и цвет состояния (`state_color`).

Важно: параметры подключения к MQTT брокеру (host/port/user/pass) в актуальном Home Assistant настраиваются через UI
(Settings → Devices & services → MQTT). YAML тут используется только для ручных MQTT-сущностей.

## Как подключить результат в Home Assistant

### MQTT-сущности

Home Assistant ожидает ручные MQTT сущности под ключом `mqtt:`. Для разбиения на несколько файлов используйте официальный
механизм `!include_dir_merge_list` (каждый файл в каталоге должен быть YAML-списком):

```yaml
mqtt: !include_dir_merge_list mqtt/
```

Этот стиль нельзя смешивать с альтернативным стилем `mqtt: { binary_sensor: [...], switch: [...] }`, и нельзя
разносить `mqtt:` несколькими include-блоками.

### Lovelace-дашборды (отдельные YAML-managed dashboards)

Чтобы не переводить основной UI-дашборд в YAML mode, подключите сгенерированные файлы как **отдельные dashboards**.
В `configuration.yaml` Home Assistant:

```yaml
lovelace:
  dashboards:
    rooms-tab-main:
      mode: yaml
      title: Rooms (generated) - Main
      icon: mdi:home-map-marker
      show_in_sidebar: true
      filename: lovelace/tab-main.yaml
    debug-generated:
      mode: yaml
      title: Debug (generated)
      icon: mdi:bug
      show_in_sidebar: true
      filename: lovelace/debug-generated.yaml
```

Файлы `lovelace/tab-*.yaml` и `lovelace/debug-generated.yaml` должны лежать в конфиг-директории HA
(обычно `/config/lovelace/`).
После изменения `configuration.yaml` перезапустите Home Assistant.

Пример структуры сгенерированного дашборда:

```yaml
title: Rooms (generated)
views:
  - title: Комнаты
    path: rooms
    icon: mdi:floor-plan
    cards:
      - type: entities
        title: Кухня
        entities:
          - switch.kitchen_light
          - switch.kitchen_fan

      - type: entities
        title: Спальня
        entities:
          - switch.bed_light
          - switch.bed_outlet
```

В реальной генерации список `entities` берётся из CSV и сортируется детерминированно.

## Как CSV превращается в сущности Home Assistant

### Обязательные колонки CSV (по заголовку)

Скрипт ищет эти заголовки в первой строке CSV:

- **`Тип`**: ожидаются значения `DI` или `DO`.
- **`sig`**: уникальный идентификатор сигнала.
- **`N`**: номер сигнала внутри "ящика" (используется только для имени системного дубликата).
- **`Имя в интерфейсе`**: человекочитаемое имя.
- **`Наименование сигнала`**: резервное имя, если "Имя в интерфейсе" пустое.
- **`Группа`**: комната (используется для карточек Lovelace-дашборда).
- **`Вкладка`**: имя вкладки (в текущей версии не используется при генерации YAML).
- **`Модуль`**, **`Я.`**: метаданные (используются для системного дубликата DO и сортировки в дашборде).
- **`MQTT name`** / **`Путь MQTT`**: MQTT путь

### Опциональные колонки

- **`Logic`**: допускается в CSV, но в текущей версии скрипта не используется.

### Правила формирования entity_id

Из колонки `sig` строится "короткое имя":

- **`sig` → `n`**: строки, точки заменяются на `_`.

Дальше в зависимости от `Тип`:

- **Если `Тип = DI`**
  - **entity_id**: `binary_sensor.<n>`
- **Если `Тип = DO`**
  - **entity_id**: `switch.<n>`

### Как формируются MQTT топики

Из колонки MQTT (`MQTT name` или `Путь MQTT`) берётся базовый путь `mqtt`, и к нему добавляются суффиксы:

- **Чтение состояния**: `state_topic = <mqtt>/p` (retained-состояние от шлюза extbus)
- **Команда записи (только DO)**: `command_topic = <mqtt>/w` (без retain)

Схема топиков extbus:

| Топик | Кто пишет | Retain |
|---|---|---|
| `/w` | HA (команды) | нет |
| `/r` | extbus (live) | нет |
| `/p` | extbus (состояние) | да |

## Связь колонок CSV с опциями Home Assistant (по генерируемым YAML)

Ниже — только то, что реально попадает в YAML.

### 1) `binary_sensor` (файл `mqtt/di.yaml`, строки `Тип = DI`)

- **`sig`**
  - влияет на: `name` (внутреннее имя в платформе) и на `entity_id` через `binary_sensor.<n>`
- **`Имя в интерфейсе`**
  - влияет на: `friendly_name`
  - если пусто, берётся **`Наименование сигнала`**
- **`Наименование сигнала`**
  - используется как запасной `friendly_name`, если "Имя в интерфейсе" пустое
- **`MQTT name` / `Путь MQTT`**
  - влияет на: `state_topic` (добавляется `/p`)
- **`Тип`**
  - определяет: что строка станет `binary_sensor` (только `DI`)

Также жёстко задаются:

- `payload_on: '1'`
- `payload_off: '0'`
- `unique_id` (стабильный идентификатор сущности)
- `default_entity_id` (полный entity_id, например `binary_sensor.<n>`; требуется для HA Core 2026.4+, где `object_id` удалён)

### 2) `switch` (файл `mqtt/do.yaml` и `mqtt/do_sys.yaml`, строки `Тип = DO`)

- **`sig`**
  - влияет на: `name` и на `entity_id` через `switch.<n>`
- **`MQTT name` / `Путь MQTT`**
  - влияет на:
    - `state_topic` (добавляется `/p`)
    - `command_topic` (добавляется `/w`)
- **`Тип`**
  - определяет: что строка станет `switch` (только `DO`)

Также жёстко задаются:

- `payload_on: '1'`
- `payload_off: '0'`
- `unique_id` (стабильный идентификатор сущности)
- `default_entity_id` (полный entity_id, например `switch.<n>`; требуется для HA Core 2026.4+, где `object_id` удалён)

Команды на `/w` **не** публикуются с retain — retained-состояние обеспечивает шлюз extbus на `/p`.
Без retained-сообщения на `state_topic` HA показывает состояние `unknown` и в UI отображает две кнопки вместо toggle.

Важно: в MQTT YAML используется поле `name` (это friendly name в UI). `customize` можно оставить, но он уже не обязателен,
если вас устраивают имена из `name`.

### 3) `customize` (файл `customize/customize_gen.yaml`, все DI и DO, включая `*_sys`)

Скрипт создаёт словарь вида:

- ключ: `binary_sensor.<n>` или `switch.<n>`
- значение: `friendly_name: ...`

Связь с CSV:

- **`sig`**
  - определяет ключ (entity_id), потому что из него строится `<n>`
- **`Имя в интерфейсе`**
  - идёт в `friendly_name`
  - если пусто, берётся **`Наименование сигнала`**
- **`Наименование сигнала`**
  - используется как запасной `friendly_name`

### 4) Lovelace-дашборды (файлы `lovelace/tab-*.yaml`)

Скрипт генерирует по одному файлу на вкладку (колонка **`Вкладка`**), каждый файл содержит один view «Комнаты»
с карточками `type: entities` по комнатам:

- **Комната** берётся из колонки **`Группа`** (отображаемое имя карточки = значение `Группа`).
- **Сущности**: только `Тип = DO` → `switch.<n>` (без системных дублей `*_sys`).
- **Пустая `Вкладка`**: строка не попадает ни в один Lovelace-файл.
- **Пустая `Группа`**: карточка `Other`.
- **`group_reserved`**: сигнал пропускается (не попадает в дашборд).
- **Сортировка** внутри комнаты: по `Я.`, затем по `N`, затем по `n`.

### 5) Lovelace debug-дашборд (файл `lovelace/debug-generated.yaml`)

Отдельный дашборд для отладки с двумя view:

- **DI** (`path: debug-di`): все `Тип = DI` → `binary_sensor.<n>`, карточки по ящику (`Box<Я.>`).
- **Sys DO** (`path: debug-sys-do`): только системные дубликаты `switch.<n>_sys`, карточки по `Box<Я.>`.

Для каждой сущности в карточке задаётся иконка (`mdi:toggle-switch` для DI, `mdi:lightbulb` для Sys DO)
и включён `state_color`, чтобы состояние on/off было видно по цвету.

- **Сортировка** внутри карточки: по `Я.`, затем по `N`, затем по `n`.

## Системные дубликаты DO (`*_sys`)

Для каждого `DO` создаётся дополнительный `switch`:

- **новый `sig`-идентификатор**: к `n` добавляется суффикс `'_sys'`
- **entity_id**: `switch.<n>_sys`
- **назначение**: технические MQTT-сущности с именами по метаданным сигнала

Как формируется `friendly_name` для `*_sys`:

- берётся из колонок **`Я.`**, **`N`**, **`Наименование сигнала`**
- формат: `<Я.>.<N> <Наименование сигнала>`

Дополнительные принудительные значения для дубликата:

- `tab = 'Sys'`
- `group = 'Box<Я.>'`
- `system = True` (это внутреннее поле скрипта; в YAML напрямую не выводится)

Системные дубликаты **не включаются** в Lovelace-дашборды `tab-*.yaml`, но **включаются** в debug-дашборд
`lovelace/debug-generated.yaml` (view «Sys DO»).
