import sys
from pathlib import Path

for f in Path(sys.argv[1]).glob('**/*'):
  fn = Path(f).name
  if (len(fn) > 60):
      print('WARN: '+fn)
