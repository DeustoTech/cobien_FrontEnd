try:
    import can
except ModuleNotFoundError:
    can = None

from icso_data.proximity_sensor_logger import log_proximity_event

CAN_INTERFACE = "can0"

SENSORS_IDS = {0x474, 0x475, 0x476, 0x477}
EVENT_CODES = {0x5EBA1ADE, 0xD157A4CE, 0xE5ABA1ED}

def parse_event_code(data):
    if data is None or len(data) < 6:
        return None
    return (data[2] << 24) | (data[3] << 16) | (data[4] << 8) | data[5]

def main():
    if can is None:
        print("[Proximity Sensor] python-can is not installed. Proximity logger disabled.")
        return
    try:
        bus = can.Bus(channel=CAN_INTERFACE, interface="socketcan")
    except Exception as exc:
        print(f"[Proximity Sensor] Unable to open {CAN_INTERFACE}: {exc}")
        return
    try:
        while True:
            msg = bus.recv(timeout=1.0)
            if msg is None:
                continue

            can_id = msg.arbitration_id
            if can_id not in SENSORS_IDS:
                continue

            event_code = parse_event_code(msg.data)
            if event_code not in EVENT_CODES:
                continue

            log_proximity_event(can_id, event_code)
    finally:
        try:
            bus.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()
