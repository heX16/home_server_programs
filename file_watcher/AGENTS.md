# file_watcher

Daemon/utility that watches files and directories under a single tree (`--dir`) and runs commands from a YAML config when they change.

Compares the current filesystem state to a YAML store (`file_comparator`); in daemon mode it wakes on watchdog events. Config sections: `commands`, `files`, `dirs`, optional `ignore`.
