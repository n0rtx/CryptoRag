import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.app import app as application

if __name__ == "__main__":
    application.run(host="127.0.0.1", port=5000, debug=False)
