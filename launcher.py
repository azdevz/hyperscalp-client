"""
launcher.py — Thin bootstrap launcher.
Imports the compiled main module and starts the FastAPI server.
This is the only .py file that will remain in the production container layer.
"""

import uvicorn
import config
from main import app

if __name__ == "__main__":
    print("=" * 60)
    print("  HYPER-SCALP-AI Launcher (Cython Compiled Runtime)")
    print(f"  Starting FastAPI server on port {config.PORT}...")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
