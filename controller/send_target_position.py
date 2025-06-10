import sys
sys.path.append("C:\\Users\\geova\\repos\\mestrado") 

from paho.mqtt import client as mqtt
from proto.target_position_pb2 import TargetPosition  # Gerado via protoc
from config.variables import BROKER, PORT  # Configurações do MQTT

TARGET_TOPIC = "fleet_manager/target_position"

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
    while True:
        try:
            entrada = input("Digite a posição alvo (x y theta): ")
            if not entrada.strip():
                continue
            partes = entrada.strip().split()

            if len(partes) < 2:
                print("Entrada inválida. Forneça pelo menos x e y.")
                continue

            x = float(partes[0])
            y = float(partes[1])
            theta = float(partes[2]) if len(partes) > 2 else 0.0

            send_target_position(x, y, theta)
        except KeyboardInterrupt:
            print("\nEncerrando envio...")
            break
        except ValueError:
            print("Entrada inválida. Certifique-se de digitar números separados por espaço.\n")

if __name__ == "__main__":
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    client.loop_start()

    main_loop()

    client.loop_stop()
    client.disconnect()
