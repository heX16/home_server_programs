import os
import sys

# This is a proxy module to import the shared file_comparator library.
# It ensures that the file_comparator_lib can be accessed correctly
# regardless of where the script is executed from.

# Adding the root directory of the project to sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
  sys.path.insert(0, _PROJECT_ROOT)

# Importing all functionality from the shared file_comparator module
from file_comparator_lib.file_comparator import *

