#!/usr/bin/env python3
"""
Test script to verify production build works.
Starts FastAPI server serving the built React app.

Usage:
    python test_prod.py

Then visit http://localhost:8000 in your browser.
"""
import os
import sys

def main():
    # Check if frontend/dist exists
    dist_path = os.path.join(os.path.dirname(__file__), "frontend", "dist")
    if not os.path.exists(dist_path):
        print("❌ Frontend not built!")
        print("Run: cd frontend && npm run build")
        sys.exit(1)

    print("✓ Frontend build found")
    print(f"  Location: {dist_path}")
    print()
    print("Starting production server...")
    print("  URL: http://localhost:8000")
    print("  Press Ctrl+C to stop")
    print()

    # Start uvicorn
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

if __name__ == "__main__":
    main()
