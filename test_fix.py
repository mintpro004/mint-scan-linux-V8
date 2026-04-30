import os
import shlex
from utils import run_cmd

def test_fixed_injection():
    # Simulate a malicious filepath
    malicious_path = "'; touch /tmp/pwned_fixed #"
    # USE shlex.quote
    quoted_path = shlex.quote(malicious_path)
    cmd = f"sudo rm -f {quoted_path} 2>/dev/null"
    
    print(f"Testing command: {cmd}")
    stdout, stderr, rc = run_cmd(cmd)
    
    if os.path.exists("/tmp/pwned_fixed"):
        print("FAILURE: Command injection still worked! /tmp/pwned_fixed was created.")
        os.remove("/tmp/pwned_fixed")
    else:
        print("SUCCESS: Command injection failed.")
        print(f"Stdout: {stdout}")
        print(f"Stderr: {stderr}")
        print(f"Return code: {rc}")

if __name__ == "__main__":
    test_fixed_injection()
