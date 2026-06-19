"""Run gen_ha_config.py against test.csv."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSV_PATH = HERE / 'test.csv'
OUT_DIR = HERE / 'out_test'
GEN_SCRIPT = HERE / 'gen_ha_config.py'


def main():
  result = subprocess.run(
    [sys.executable, str(GEN_SCRIPT), f'--csv={CSV_PATH}', f'--out={OUT_DIR}'],
    cwd=HERE,
  )
  sys.exit(result.returncode)


if __name__ == '__main__':
  main()
