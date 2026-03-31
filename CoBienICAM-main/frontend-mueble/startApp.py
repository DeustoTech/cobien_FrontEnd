import subprocess
import sys
import os
# from face_authentication.authentication import authenticate_user
from face_authentication.authentication_guest import authenticate_user


def lanzar_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_app_path = os.path.join(base_dir, "mainApp.py")
    subprocess.Popen([sys.executable, main_app_path], cwd=base_dir)

def main():
    name = authenticate_user()
    if name:
        lanzar_app()

if __name__ == "__main__":
    main()
