"""Start backend — kills old process on port, then starts uvicorn."""
import os
import subprocess
import sys
from pathlib import Path


def main():
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8014

    # Ensure we're in the project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    sys.path.insert(0, str(project_root))

    # Kill any process on the target port (Windows)
    result = subprocess.run(["cmd", "/c", f"netstat -ano | findstr :{PORT}"], capture_output=True, text=True)
    for line in result.stdout.split("\n"):
        if "LISTENING" in line:
            pid = line.strip().split()[-1]
            subprocess.run(["cmd", "/c", f"taskkill /F /PID {pid}"], capture_output=True)
            print(f"Killed PID {pid} on port {PORT}")

    # Start uvicorn
    from uvicorn import run
    run("api.main:app", host="0.0.0.0", port=PORT, reload=True)


if __name__ == "__main__":
    main()

