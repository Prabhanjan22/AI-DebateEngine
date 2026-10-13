"""
run.py - Convenience script to start the Multi-Agent AI Debate System locally.
Usage:
    python run.py
"""

import sys
import os
from pathlib import Path
import uvicorn

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Starting Multi-Agent AI Debate Platform locally...")
    print("  Access the app at: http://localhost:8000/app/")
    print("  API Documentation at: http://localhost:8000/docs")
    print("=" * 60 + "\n")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
