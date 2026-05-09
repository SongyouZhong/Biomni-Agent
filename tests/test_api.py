import sys
import os
import time
import subprocess
import requests

def main():
    print("1. Starting FastAPI server...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(".")
    
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8080"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    print("2. Waiting for server to initialize...")
    time.sleep(5)
    
    # Check if process is still running
    if process.poll() is not None:
        print(f"Server crashed with exit code {process.returncode}")
        print("STDOUT:", process.stdout.read())
        print("STDERR:", process.stderr.read())
        sys.exit(1)
        
    print("3. Sending test request to /docs...")
    try:
        response = requests.get("http://127.0.0.1:8080/docs", timeout=5)
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print("SUCCESS: API Gateway is up and running!")
        else:
            print("FAILED: Unexpected status code.")
    except Exception as e:
        print(f"FAILED: Could not connect to API Gateway. Error: {e}")
        
    print("4. Shutting down server...")
    process.terminate()
    process.wait(timeout=5)
    print("Done.")

if __name__ == "__main__":
    main()
