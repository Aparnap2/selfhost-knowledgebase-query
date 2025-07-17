import sys
import os
import time

def check_health():
    # Check if the Python application is running correctly
    try:
        # Perform a simple test, e.g. import a module or call a function
        import pandas as pd
        pd.DataFrame({'A': [1, 2, 3]})
        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

if __name__ == "__main__":
    # Retry the health check a few times in case of temporary issues
    for _ in range(3):
        if check_health():
            sys.exit(0)
        time.sleep(5)
    sys.exit(1)
