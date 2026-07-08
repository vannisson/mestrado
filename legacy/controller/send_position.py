import sys
import time
sys.path.append("C:\\Users\\geova\\repos\\mestrado") 

from paho.mqtt import client as mqtt
from proto.target_position_pb2 import TargetPosition  # Gerado via protoc
from config.variables import BROKER, PORT  # Configurações do MQTT

TARGET_TOPIC = "fleet_manager/target_position"
SEND_INTERVAL = 4  # tempo (em segundos) entre cada mensagem

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "target_sender")

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Conectado ao broker MQTT.")
    else:
        print(f"Falha na conexão. Código: {reason_code}")

def send_target_position(x, y, theta=0.0):
    target = TargetPosition()
    target.x = x
    target.y = y
    target.theta = theta

    payload = target.SerializeToString()
    client.publish(TARGET_TOPIC, payload)
    print(f"> Enviado: x={x}, y={y}, theta={theta}")

def main_loop():
    """
    Itera automaticamente por valores inteiros de x e y,
    de -2 até 4 (inclusive), enviando um TargetPosition para cada par.
    """
    for x in range(-2, 5):        # -2, -1, 0, 1, 2, 3, 4
        for y in range(-2, 5):    # -2, -1, 0, 1, 2, 3, 4
            send_target_position(float(x), float(y), 0.0)
            time.sleep(SEND_INTERVAL)
    print("Envio automático concluído.")

if __name__ == "__main__":
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    client.loop_start()

    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nEnvio interrompido manualmente.")
    finally:
        client.loop_stop()
        client.disconnect()
