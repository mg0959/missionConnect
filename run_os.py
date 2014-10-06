import platform, os
if platform.system() == "Windows":
    os.system("flask\Scripts\python run.py")
else:
    os.system("./ run.py")
