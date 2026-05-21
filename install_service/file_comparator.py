import sys
import os

# This is a proxy module to import the shared `file_comparator_lib` library.

# Adding the root directory of the project to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importing all functionality from the shared file_comparator module
from file_comparator_lib.file_comparator import *
