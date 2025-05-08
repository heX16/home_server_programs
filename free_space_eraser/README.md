# Free Space Eraser

A simple Python utility for securely erasing free space on a disk by filling it with zeros.

## Purpose

This tool creates a temporary file that consumes almost all available free space on a specified disk, writes zeros to it, and then deletes the file. This process helps to ensure that deleted data cannot be recovered.

## Requirements

- Python 3.6+
- tqdm library for progress display

## Installation

Install the required dependency:

```bash
pip install tqdm
```

## Usage

```bash
python free_space_eraser.py /path/to/directory
```

Where `/path/to/directory` is any directory on the disk you want to erase free space on.

## How it works

1. The program determines the available free space on the disk containing the specified path
2. It creates a file that is 1MB smaller than the total free space (rounded down to the nearest MB)
3. The file is filled with zeros (showing progress with a progress bar)
4. Once complete, the file is automatically deleted

## Notes

- The program leaves 1MB of free space to prevent the disk from becoming completely full
- This utility is designed for Linux systems
- You may need to run with elevated privileges if writing to system directories