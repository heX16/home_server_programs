#!/bin/sh -e

journalctl -u home-extbus-uart.service -n 100 --no-pager
