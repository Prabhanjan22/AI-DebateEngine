"""
main.py - Root entry point redirecting to backend.main:app
Usage:
    python main.py
    uvicorn main:app --reload
"""

import sys
from pathlib import Path
import uvicorn

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.main import app

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Starting Multi-Agent AI Debate Platform locally...")
    print("  Access the app at: http://localhost:8000/app/")
    print("  API Documentation at: http://localhost:8000/docs")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
