import os
import sys
from pathlib import Path

# Add backend directory to sys.path so 'config' and 'planner' modules are found
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from backend.config.wsgi import application
app = application
