


# `service_list.yaml` example:
```
dyndns.service:
  mtime: 2026-05-19_15:51:10Z
  type: file
  systemd:
    status: active/running
    unit_file_state: enabled
    result: success
    exec_main_status: '0'
dyndns.timer:
  mtime: 2026-05-19_11:21:07Z
  type: file
  systemd:
    status: active/waiting
    unit_file_state: enabled
    result: success
    exec_main_status: '0'
fscrypt.service:
  mtime: 2026-05-08_23:02:22Z
  type: file
  systemd:
    status: failed/failed
    unit_file_state: enabled
    result: exit-code
    exec_main_status: '1'
    logs:
      1: May 21 12:00:01 host fscrypt[1234]: Fatal error: config missing
      2: May 21 12:00:01 host systemd[1]: fscrypt.service: Main process exited, code=exited, status=1/FAILURE
      3: May 21 12:00:01 host systemd[1]: fscrypt.service: Failed with result 'exit-code'.
      4: May 21 12:00:00 host fscrypt[1234]: Starting fscrypt...
      5: May 21 12:00:00 host systemd[1]: Started fscrypt.service.
```


