---
name: IPv4 support for dyndns
overview: Добавить поддержку IPv4 (A) с автоопределением внешнего адреса, сохранив совместимость текущего IPv6 сценария (AAAA) и поведение провайдеров FreeDNS/DuckDNS.
todos:
  - id: cli-family
    content: Обновить usage/docopt и добавить `--family` (и при желании `--ipv4-url`).
    status: pending
  - id: ipv4-detect
    content: Реализовать `get_public_ipv4()` с fallback по нескольким сервисам и валидацией через `ipaddress`.
    status: pending
  - id: duckdns-both
    content: Расширить `duckdns_update` для отправки `ip` (IPv4) и `ipv6` (IPv6) в одном запросе, если доступны.
    status: pending
  - id: freedns-family
    content: Добавить выбор адреса для FreeDNS по `--family`, и поддержку `both` через FreeDNS v2 sync интерфейс (2 HTTP-запроса за один запуск, один и тот же токен).
    status: pending
  - id: manual-check
    content: Прогнать ручные проверки для DuckDNS и FreeDNS сценариев (v4/v6/both/auto).
    status: pending
isProject: false
---

## Цель
Добавить в `[h:\Pyt\home_server_programs\dyndns\dyndns_v6.py](h:\Pyt\home_server_programs\dyndns\dyndns_v6.py)` поддержку **IPv4** с автоопределением внешнего IP через внешний сервис, и обновление DNS:
- **DuckDNS**: за один запуск уметь обновлять **A и AAAA** (если найден хотя бы один адрес).
- **FreeDNS**: за один запуск передавать **один токен** (как ты попросил), но при этом поддержать режим `both` через **v2 sync интерфейс**: за один запуск сделать **2 HTTP-запроса** (IPv4 endpoint + IPv6 endpoint) с **тем же токеном**, и обновить столько записей, сколько привязано к этому update key (в v2 UI есть “clone master”, который позволяет одним ключом обновлять несколько записей).

## Текущее состояние (что есть сейчас)
- Скрипт определяет IPv6 локально через `ip -6 route get ...` (`get_ipv6_src`) и обновляет:
  - FreeDNS: параметр `address=`
  - DuckDNS: параметр `ipv6=`
- IPv4 сейчас не определяется и не отправляется.

## Предлагаемые изменения
### 1) CLI/конфигурация
Обновить usage/docstring и `docopt`-опции:
- Добавить опцию семейства адресов:
  - `--family=auto|v4|v6|both` (по умолчанию `auto`)
  - Для **DuckDNS** допустимо `both`.
- Добавить опцию для FreeDNS API (чтобы не ломать текущий формат токена):
  - `--freedns-api=v1|v2` (по умолчанию `v1`)
  - `v1` = текущий `dynamic/update.php?...&address=...`
  - `v2` = `https://sync.afraid.org/u/<token>/` и `https://v6.sync.afraid.org/u/<token>/` (см. примеры на главной FreeDNS и в v2 guide)
  - Для **FreeDNS** `--family=both` разрешаем только при `--freedns-api=v2` (так как это реально “два запроса за один запуск”).
- (Опционально) `--ipv4-url=URL` для ручного выбора сервиса определения внешнего IPv4 (если не задано — используем список по умолчанию).
- Сохранить обратную совместимость:
  - `dyndns_v6.py TOKEN [INTERFACE]` продолжает работать как FreeDNS-режим по умолчанию.

### 2) Автоопределение внешнего IPv4
Добавить функцию наподобие `get_public_ipv4()`:
- Делает HTTP GET к нескольким сервисам по очереди (fallback), например:
  - `https://api.ipify.org`
  - `https://icanhazip.com`
  - `https://ifconfig.me/ip`
- Валидирует ответ через стандартный модуль `ipaddress` (IPv4), отбрасывает мусор.
- Таймаут использовать тот же `HTTP_TIMEOUT_S`.

### 3) Логика выбора адресов перед обновлением
В `main()`:
- Пытаемся получить IPv6 как сейчас (`get_ipv6_src`).
- Пытаемся получить IPv4 через внешний сервис.
- Если `--family=v4` — используем только IPv4; если не получилось — ошибка.
- Если `--family=v6` — используем только IPv6; если не получилось — ошибка.
- Если `--family=auto`:
  - Для DuckDNS: отправляем всё, что нашли (ipv4 и/или ipv6).
  - Для FreeDNS:
    - при `--freedns-api=v1`: отправляем **IPv6 если есть**, иначе **IPv4** (одна запись/одно обновление).
    - при `--freedns-api=v2`: отправляем всё, что нашли (как “both”, но без требования иметь оба).
- Если `--family=both`:
  - DuckDNS: отправляем оба, но если один не найден — всё равно обновляем вторым.
  - FreeDNS:
    - при `--freedns-api=v1`: возвращаем понятную ошибку (в этом режиме один запрос обновляет один адрес/тип).
    - при `--freedns-api=v2`: делаем 2 запроса (IPv4 + IPv6) и считаем успехом, если успешно выполнился хотя бы один из них.

### 4) Обновление провайдеров
- **DuckDNS**: изменить `duckdns_update(...)` так, чтобы принимал `ipv4: str | None` и `ipv6: str | None` и собирал query только с доступными параметрами:
  - IPv4 параметр в DuckDNS — `ip`
  - IPv6 параметр — `ipv6`
  - Если есть хотя бы один из них — запрос выполняем.
- **FreeDNS**:
  - `v1`: оставить текущий `freedns_update(token, address)` (параметр `address=` будет либо IPv4, либо IPv6).
  - `v2`: добавить `freedns_v2_update(token: str, ip: str, ip_version: Literal['v4','v6'])`, который ходит на:
    - IPv4: `https://sync.afraid.org/u/<token>/?ip=<ipv4>` (или без `ip=`, но безопаснее передавать явно)
    - IPv6: `https://v6.sync.afraid.org/u/<token>/?ip=<ipv6>`
    - Для `--family=both` вызвать оба запроса, но не падать, если один из IP не определился.

### 5) Вывод/коды ошибок
- Печатать найденные адреса:
  - `IPv4: ...` если найден
  - `IPv6: ...` если найден
- Успех:
  - Для DuckDNS: успех, если ответ `OK` и мы отправляли хотя бы один IP.
  - Для FreeDNS: успех, если запрос прошёл без исключения (как сейчас).
- Ошибка:
  - Если не удалось определить ни IPv4, ни IPv6 (в соответствии с `--family`) — завершать с кодом 1.

## Мини-проверка (ручная)
- DuckDNS:
  - `--provider=duckdns --domains=... --token=... --family=both`
  - Проверить, что в ответе `OK` и что A/AAAA обновились.
- FreeDNS:
  - `v1`:
    - Запуск с токеном и `--family=v4` (обновление A).
    - Запуск с токеном и `--family=v6` (обновление AAAA).
  - `v2`:
    - Взять update key из `Dynamic DNS v2 interface` (и при необходимости настроить “clone master”, чтобы один ключ обновлял несколько записей).
    - Запуск `--freedns-api=v2 --family=both` и проверить, что обновились A и AAAA (если оба IP определились).

## Файлы
- Изменения только в `[h:\Pyt\home_server_programs\dyndns\dyndns_v6.py](h:\Pyt\home_server_programs\dyndns\dyndns_v6.py)`.
