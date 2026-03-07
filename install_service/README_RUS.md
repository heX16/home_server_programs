Установка systemd‑юнитов из синхронизируемой папки
==================================================

`install_service.py` устанавливает и обновляет unit‑файлы `systemd` из
локального каталога, синхронизируемого с сервером (например, через Syncthing).

Скрипт определяет:

- новые unit‑файлы;
- удалённые unit‑файлы;
- изменённые unit‑файлы

и выполняет нужные команды `systemctl` (копирование, enable, start, stop,
disable, daemon‑reload, reset‑failed).


Использование
-------------

Запускайте скрипт на сервере, где расположен каталог
`/opt/homesrv/home_server_programs`:

```bash
cd /opt/homesrv/home_server_programs/install_service
./install_service.py --dir=PATH --store=FILE
```

Аргументы:

- `--dir=PATH` – путь к локальному каталогу с unit‑файлами;
- `--store=FILE` – YAML‑файл с сохранённым состоянием
  (по умолчанию в скрипте: `service_list.yaml`).

Обычно скрипт вызывают из cron, systemd‑таймера или вручную после изменения
unit‑файлов в синхронизируемой папке.

