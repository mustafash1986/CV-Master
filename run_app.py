"""
Launcher script for CV Servant Desktop Application.
"""
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from cv_servant.gui.main_window import launch_app

if __name__ == "__main__":
    launch_app()
