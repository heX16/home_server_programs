#!/bin/sh
# `usermod -aG GROUPS USER` adds USER to groups GROUPS

# Examples:
# `add_user_to_groups syncthing share`
# Result:
# user `syncthing` has access to group `share`.
# user `share` still cannot read group `syncthing`.

# add_user_to_groups USER GROUP1[,GROUP2,...] — add USER to groups (USER first, then comma-separated groups)
add_user_to_groups() {
  user=$1
  groups=$2
  [ -n "$user" ] && [ -n "$groups" ] && usermod -a -G "$groups" "$user"
}

groupadd share

add_user_to_groups syncthing   dialout
add_user_to_groups syncthing   syncthing

add_user_to_groups openhab     share
add_user_to_groups syncthing   share
add_user_to_groups sambashare  share

add_user_to_groups syncthing   share,www-data
add_user_to_groups root        share,syncthing,www-data

add_user_to_groups www-data    syncthing

# add_user_to_groups debian-transmission     share
# not secure: add_user_to_groups www-data    share
