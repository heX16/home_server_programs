#!/bin/bash
# Example: filewatcher.sh /home/target_path

# watchmedo - не работает, зависает! (сжирает весь проц)

if [ -z "$1" ] ; then
    echo "Example: filewatcher.sh /home/target_path"
    exit
fi

ps -ef | grep -E ".*watchmedo shell-command .* $1$" | awk '{print $2}' | xargs --no-run-if-empty kill
watchmedo shell-command --recursive --wait --interval 5.0 --command='${PWD}/access_cmd.sh "${watch_src_path}"' $1   1>/dev/null 2>/dev/null &



# watchmedo shell-command --recursive --wait --interval 5.0 --command=\'chown -f :share ${watch_src_path} & chmod -f g+rw ${watch_src_path}\' $1 &
