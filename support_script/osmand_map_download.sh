#!/bin/sh

# apt install bsdtar

if [ -d "/home/syncthing/osmand/" ]; then
  # DIR exists.
  cd /home/syncthing/osmand/
  mkdir download
else
  exit 1
fi


# download

# https://download.osmand.net/list.php
# http://download.osmand.net/download?standard=yes&file=Russia_nizhegorod_asia_2.obf.zip
# http://download.osmand.net/download?standard=yes&file=Serbia_europe_2.obf.zip

# curl -L https://dl7.osmand.net/download?standard=yes\&file=Russia_nizhegorod_asia_2.obf.zip | bsdtar -xvf - -C ./

#    --header="Accept: text/html" --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:93.0) Gecko/20100101 Firefox/93.0" \
#    --save-cookies osmand_cookies.txt \
#    --keep-session-cookies \

# doc:
# --output-document Если file указан, как -, то документы будут выводиться на стандартный вывод (stdout).



wget \
     --output-document - \
     http://download.osmand.net/download?standard=yes\&file=Serbia_europe_2.obf.zip \
     | bsdtar -xvf - -C ./download/

if [ -f "./download/Serbia_europe_2.obf" ]; then
  rm ./Serbia_europe_2.obf
  mv ./download/Serbia_europe_2.obf ./
else
  exit 2
fi



wget \
     --output-document - \
     http://download.osmand.net/download?standard=yes\&file=Russia_nizhegorod_asia_2.obf.zip \
     | bsdtar -xvf - -C ./download/

if [ -f "./download/Russia_nizhegorod_asia_2.obf" ]; then
  rm ./Russia_nizhegorod_asia_2.obf
  mv ./download/Russia_nizhegorod_asia_2.obf ./
else
  exit 2
fi

