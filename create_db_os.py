import platform, os
if platform.system() == "Windows":
    os.system("flask\Scripts\python db_create.py")
else:
    os.system("./ db_create.py")
