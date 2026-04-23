#!/usr/bin/env python3

import fnmatch
import grp
import logging
import os
import pwd
import stat
import sys
from typing import Callable, Iterator, Sequence


SinglePathOp = Callable[[str], None]

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s',
    )


def directory_exists(path: str) -> bool:
    if not os.path.isdir(path):
        logger.warning('cannot access %s, skipping', path)
        return False
    return True


def iter_paths(root: str) -> Iterator[str]:
    yield root
    for current_root, dirs, files in os.walk(root):
        for dir_name in dirs:
            yield os.path.join(current_root, dir_name)
        for file_name in files:
            yield os.path.join(current_root, file_name)


def resolve_chown_ids(user: str, group: str) -> tuple[int, int]:
    uid = pwd.getpwnam(user).pw_uid if user else -1
    gid = grp.getgrnam(group).gr_gid if group else -1
    return uid, gid


def ensure_owner(path: str, uid: int, gid: int) -> None:
    stats = os.lstat(path)
    target_uid = stats.st_uid if uid == -1 else uid
    target_gid = stats.st_gid if gid == -1 else gid
    if stats.st_uid == target_uid and stats.st_gid == target_gid:
        return
    os.chown(path, uid, gid, follow_symlinks=False)


def ensure_mode(path: str, new_mode: int) -> None:
    current_mode = stat.S_IMODE(os.lstat(path).st_mode)
    if current_mode == new_mode:
        return
    os.chmod(path, new_mode, follow_symlinks=False)


def apply_add_group_write_one(path: str) -> None:
    current_mode = stat.S_IMODE(os.lstat(path).st_mode)
    ensure_mode(path, current_mode | stat.S_IWGRP)


def apply_execute_patterns_one(path: str, patterns: Sequence[str]) -> None:
    if not os.path.isfile(path):
        return
    file_name = os.path.basename(path)
    if not any(fnmatch.fnmatch(file_name, pattern) for pattern in patterns):
        return
    current_mode = stat.S_IMODE(os.lstat(path).st_mode)
    ensure_mode(path, current_mode | 0o555)


def apply_group_rwX_others_none_one(path: str) -> None:
    stats = os.lstat(path)
    mode = stat.S_IMODE(stats.st_mode)
    updated = mode | stat.S_IRGRP | stat.S_IWGRP
    updated &= ~(stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH)
    is_directory = stat.S_ISDIR(stats.st_mode)
    has_any_execute = bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    if is_directory or has_any_execute:
        updated |= stat.S_IXGRP
    else:
        updated &= ~stat.S_IXGRP
    ensure_mode(path, updated)


def apply_setgid_directory_one(path: str) -> None:
    if not os.path.isdir(path):
        return
    current_mode = stat.S_IMODE(os.lstat(path).st_mode)
    ensure_mode(path, current_mode | stat.S_ISGID)


def apply_non_recursive(root: str, operations: Sequence[SinglePathOp]) -> None:
    for operation in operations:
        operation(root)


def walk_tree(root: str, operations: Sequence[SinglePathOp]) -> None:
    for path in iter_paths(root):
        for operation in operations:
            operation(path)


def run_if_directory_exists(
    path: str,
    root_only_operations: Sequence[SinglePathOp],
    tree_operations: Sequence[SinglePathOp],
) -> None:
    if not directory_exists(path):
        return
    apply_non_recursive(path, root_only_operations)
    if tree_operations:
        walk_tree(path, tree_operations)


def configure_tree(
    path: str,
    user: str,
    group: str,
    *,
    add_group_write: bool = False,
    execute_file_patterns: Sequence[str] | None = None,
    group_rwX_others_none: bool = False,
    setgid_directories: bool = False,
) -> None:
    """Apply ownership and optional mode rules under path.

    Empty user or group means do not change that attribute (os.chown -1).
    If both user and group are empty, the ownership step is skipped entirely.

    root_only_operations run once on path. tree_operations run on every node
    under path in a single walk; each operation touches only that path.
    """
    root_only_ops: list[SinglePathOp] = []
    tree_ops: list[SinglePathOp] = []

    if user or group:
        uid, gid = resolve_chown_ids(user, group)
        tree_ops.append(lambda p, u=uid, g=gid: ensure_owner(p, u, g))
    if add_group_write:
        tree_ops.append(apply_add_group_write_one)
    if execute_file_patterns:
        patterns = tuple(execute_file_patterns)
        tree_ops.append(lambda p, pat=patterns: apply_execute_patterns_one(p, pat))
    if group_rwX_others_none:
        tree_ops.append(apply_group_rwX_others_none_one)
    if setgid_directories:
        tree_ops.append(apply_setgid_directory_one)
    run_if_directory_exists(path, root_only_ops, tree_ops)


def ensure_root_user() -> None:
    if os.geteuid() != 0:
        logger.error('this script must be run as root.')
        sys.exit(1)


def main() -> None:
    setup_logging()
    ensure_root_user()
    logger.info('Setting the access rights.')
    configure_tree(
        '/opt/hspro',
        'root',
        'share',
        add_group_write=True,
        execute_file_patterns=(
            '*.sh',
            '*.elf',
            '*.exec.??',
            '*.exec.???',
        ),
    )
    configure_tree(
        '/srv/config',
        'root',
        'share',
        group_rwX_others_none=True,
        setgid_directories=True,
    )
    configure_tree(
        '/etc/openhab2',
        'openhab',
        'share',
        add_group_write=True,
    )


if __name__ == '__main__':
    main()
