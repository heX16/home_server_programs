import sys
import os

# This is a proxy module to import the shared library.
# It ensures that the `*_lib` can be accessed correctly
# regardless of where the script is executed from.

# Adding the root directory of the project to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importing all functionality from the shared module
from easy_timer_lib.easy_timer import *
