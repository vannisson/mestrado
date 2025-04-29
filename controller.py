import time
import keyboard
from paho.mqtt import client as mqtt
from data.twist_pb2 import Twist  
from config import BROKER, PORT, CONTROL_TOPIC

COPPELIA_CLIENT = "coppelia"
AGV_CLIENT = "agv"

LINEAR_SPEED = 0.5  # m/s
ANGULAR_SPEED = 1.0  # rad/s

linear_x = 0.0
angular_z = 0.0

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "keyboard_controller")

def publish_cmd_vel():
    twist_msg = Twist()
    twist_msg.linear_x = linear_x
    twist_msg.angular_z = angular_z
    payload = twist_msg.SerializeToString()

    for target_client in [COPPELIA_CLIENT, AGV_CLIENT]:
      topic = CONTROL_TOPIC.replace("CLIENT", target_client)
      client.publish(topic, payload)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker!")
    else:
        print(f"Failed to connect, return code {reason_code}")

def main_loop():
    global linear_x, angular_z

    print("Use WASD to move. SPACE to stop. ESC to exit.")

    while True:
        if keyboard.is_pressed('w'):
            linear_x = LINEAR_SPEED
            angular_z = 0.0
            publish_cmd_vel()
            time.sleep(0.1)

        elif keyboard.is_pressed('s'):
            linear_x = -LINEAR_SPEED
            angular_z = 0.0
            publish_cmd_vel()
            time.sleep(0.1)

        elif keyboard.is_pressed('a'):
            linear_x = 0.0
            angular_z = ANGULAR_SPEED
            publish_cmd_vel()
            time.sleep(0.1)

        elif keyboard.is_pressed('d'):
            linear_x = 0.0
            angular_z = -ANGULAR_SPEED
            publish_cmd_vel()
            time.sleep(0.1)

        elif keyboard.is_pressed('space'):
            linear_x = 0.0
            angular_z = 0.0
            publish_cmd_vel()
            time.sleep(0.1)

        elif keyboard.is_pressed('esc'):
            print("Exiting...")
            break

        time.sleep(0.01)

if __name__ == "__main__":
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    client.loop_start()
    main_loop()
    client.loop_stop()
    client.disconnect()
