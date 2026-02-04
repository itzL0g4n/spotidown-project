import urllib.request
import sys

url = "https://bootstrap.pypa.io/get-pip.py"
try:
    print("Downloading get-pip.py...")
    urllib.request.urlretrieve(url, "get-pip.py")
    print("Download complete.")
except Exception as e:
    print(f"Error downloading: {e}")
    sys.exit(1)
