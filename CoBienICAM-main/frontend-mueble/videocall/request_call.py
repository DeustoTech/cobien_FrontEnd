from kivy.uix.button import Button
import requests

def send_pizarra_notification(
    to_user: str,
    api_key: str = "test_jules",
    message: str = "Call now?",
    from_device: str = "Maria"
):
    url = "http://portal.co-bien.eu/pizarra/api/notify/"

    data = {
        "to_user": to_user,
        "from_device": from_device,
        "kind": "call_ready",
        "message": message,
        "ttl_hours": 12
    }

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(url, json=data, headers=headers)
        print("Status:", r.status_code)
        print("Response:", r.text)
        return r
    except Exception as e:
        print("Erreur en envoyant la notification :", e)
        return None
