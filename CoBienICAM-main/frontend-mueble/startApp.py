import subprocess
# from face_authentication.authentication import authenticate_user
from face_authentication.authentication_guest import authenticate_user


def lanzar_app():
    subprocess.Popen(["python", "mainApp.py"])

def main():
    name = authenticate_user()
    if name:
        lanzar_app()

if __name__ == "__main__":
    main()
