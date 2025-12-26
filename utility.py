import subprocess
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.Popen([sys.executable, "gen.py"])
subprocess.Popen([sys.executable, "utility.py"])
