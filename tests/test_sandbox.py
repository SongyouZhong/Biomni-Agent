import requests
import time

def test_sandbox():
    print("Sending test code to sandbox...")
    try:
        response = requests.post(
            "http://localhost:8081/execute", 
            json={"code": "import sys\nprint('Hello from the isolated Sandbox!')\nprint(f'Python version: {sys.version}')"},
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ Sandbox execution successful!")
                print("--- Stdout ---")
                print(result["stdout"].strip())
                print("--------------")
            else:
                print("❌ Sandbox returned an error:")
                print(result.get("error"))
        else:
            print(f"❌ Failed with status code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Sandbox. Make sure the Docker container is running on port 8081.")

if __name__ == "__main__":
    test_sandbox()
