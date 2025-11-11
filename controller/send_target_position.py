# controller/send_target_position.py

from paho.mqtt import client as mqtt
from proto.target_position_pb2 import TargetPosition
from config.variables import BROKER, PORT
import time

def send_target_position(x: float, y: float, theta: float = 0.0):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER, PORT)
    client.loop_start()  # garante processamento do publish

    msg = TargetPosition(x=x, y=y, theta=theta)
    payload = msg.SerializeToString()

    result = client.publish("fleet_manager/target_position", payload, qos=1)
    result.wait_for_publish()  # bloqueia até o envio realmente ocorrer

    time.sleep(0.1)  # pequena pausa para garantir envio antes de desconectar
    client.loop_stop()
    client.disconnect()
