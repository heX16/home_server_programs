#!/usr/bin/env python3
import os
import sys
import shutil
import tqdm
import pathlib

def get_disk_free_space(path):
    """Get free space in bytes on the disk containing the path."""
    stats = shutil.disk_usage(path)
    return stats.free

def erase_free_space(path):
    """Create a file that fills most of the free space and fill it with zeros."""
    # Ensure the path exists
    path_obj = pathlib.Path(path)
    if not path_obj.exists():
        os.makedirs(path, exist_ok=True)

    # Get free space and calculate file size (leave 1MB free)
    free_space = get_disk_free_space(path)
    one_mb = 1024 * 1024
    file_size = free_space - one_mb

    # Round down to nearest MB
    file_size = (file_size // one_mb) * one_mb

    if file_size <= 0:
        print(f"Not enough free space on disk ({free_space} bytes available)")
        return

    # Create the file path
    fill_file = os.path.join(path, "free_space.fill")

    try:
        print(f"Creating file of size {file_size // one_mb} MB at {fill_file}")

        # Create and fill the file with zeros
        chunk_size = 1 * one_mb  # Write in 1MB chunks
        total_chunks = file_size // chunk_size

        with open(fill_file, 'wb') as f:
            # Use tqdm for progress bar
            for _ in tqdm.tqdm(range(total_chunks), desc="Writing zeros", unit="MB"):
                f.write(b'\0' * chunk_size)

        print("Free space has been filled with zeros")

    except Exception as e:
        print(f"Error while filling free space: {e}")

    finally:
        # Delete the file
        if os.path.exists(fill_file):
            print(f"Deleting file {fill_file}")
            os.remove(fill_file)
            print("File deleted successfully")

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"Target path: {path}")
    print(f"Free space before: {get_disk_free_space(path) // (1024*1024)} MB")

    erase_free_space(path)

    print(f"Free space after: {get_disk_free_space(path) // (1024*1024)} MB")

if __name__ == "__main__":
    main()