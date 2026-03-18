@echo off
cd /d "%~dp0"
python "..\watcher.py" --dir=..\.. --store=watcher_store_test.yaml --config=watcher_config_test.yaml
pause