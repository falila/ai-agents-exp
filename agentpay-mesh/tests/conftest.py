import os
import sys

# Ensure the package source directory is on the PYTHONPATH during pytest collection.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
