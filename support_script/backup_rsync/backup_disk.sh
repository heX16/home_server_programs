#!/bin/sh

./mount_disk.sh

sudo rsync --archive --one-file-system --hard-links --sparse --acls --xattrs --delete-during --delete-excluded --numeric-ids --info=progress2 \
     --include-from=backup_include.txt \
     --exclude-from=backup_ignore.txt \
     /mnt/rpi64/  \
     /mnt/rpi64backup/

# 9adb8e47 - 64gb FLASH (f2fs)
# 529c21d7 - virtual disk for backup (ext4)

# --include-from=backup_include.txt

# sudo rsync -axHAWXS --delete-before --numeric-ids --info=progress2 --exclude-from=backup_ignore.txt --include-from=backup_include.txt /media/root/9adb8e47-ed70-4c5b-ac64-96f395c3d09c/ /media/root/529c21d7-8095-4862-8b50-724de09cbb48/

#   https://qastack.ru/superuser/156664/what-are-the-differences-between-the-rsync-delete-options
#  --delete-before
# --del                   an alias for --delete-during
# --delete                delete extraneous files from dest dirs
# --delete-before         receiver deletes before transfer (default)
# --delete-during         receiver deletes during xfer, not before
# --delete-delay          find deletions during, delete after
# --delete-after          receiver deletes after transfer, not before
# --delete-excluded       also delete excluded files from dest dirs

#  --sparse                handle sparse files efficiently
#  --acls                  preserve ACLs (implies -p)
#  --xattrs                preserve extended attributes
