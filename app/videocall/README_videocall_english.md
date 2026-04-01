# Video Call Module – CoBien Project

This system enables video calls between an elderly person using the smart furniture and a family member through the CoBien project web portal.

## General Description

When a family member starts a video call from the project’s website, an MQTT notification is sent to the furniture. The device then displays a text and voice message informing the user. If the user presses the “Start Video Call” button, an independent window (created with PyQt5) opens with the video call already active.

---

## Operation Flow

1. The website initiates a video call → sends an MQTT message to the `videollamada` topic with the family member’s name.  
2. The Kivy app on the furniture is always subscribed to the MQTT topic, and upon receiving the message:
   - Displays a message on screen: `Incoming video call from Pedro`
   - Plays a voice alert: `You have a video call from Pedro`
   - Waits for the user to press the “Start Video Call” button  
3. When the user presses the button:
   - The script `videocall_launcher.py` is executed, which opens the page: https://portal.co-bien.eu/videocall/
   - The necessary data is automatically filled in thanks to `CustomWebEnginePage`.

---

## File Structure

```
videocall/
├── videocallScreen.py       # Kivy screen with the video call button
├── videocall_launcher.py    # PyQt5 window that opens the video call in an embedded browser
```

---

## Technical Details

### 1. MQTT
- Uses the public HiveMQ broker: `broker.hivemq.com`
- The Kivy app subscribes to two topics:
  - `tarjeta` → for NFC card navigation  
  - `videollamada` → for video calls  
- The website acts as the publisher. The `mqtt_publisher.py` script is only for testing.

### 2. Embedded Browser with PyQt5
- Uses `QWebEngineView` to display the video call portal.  
- Microphone and camera permissions are automatically granted (`--use-fake-ui-for-media-stream`).  
- An automatic prompt with the name “Maria” is used to complete access.

---

## How to Start a Video Call

From the furniture interface:
1. Receive an MQTT notification from the web.  
2. Press the “Start Video Call” button.  
3. `videocall_launcher.py` is launched in a new window.  
4. The embedded browser opens the URL: https://portal.co-bien.eu/videocall/

---

## Additional Notes

- If the PyQt5 window is closed, the app automatically returns to the main screen.  
- `videocall_launcher.py` can be launched independently for testing.  
