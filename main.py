from paho.mqtt import client as mqtt
import math 

CLIENT_NAME = "pioneer"

topics = [
    # IMU
    f"{CLIENT_NAME}/imu/linearVelocity",
    f"{CLIENT_NAME}/imu/angularVelocity",
    # Odometry
    f"{CLIENT_NAME}/odometry/pose",
    f"{CLIENT_NAME}/odometry/wheel_vel",
    # Sensor
    f"{CLIENT_NAME}/sensor/ranges",
    f"{CLIENT_NAME}/sensor/intensities",
]
        
def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("Connected to MQTT Broker!")
            
            for topic in topics:
                client.subscribe(topic)
                print(f"Subscribed to: {topic}")

        else:
            print("Failed to connect, return code %d\n", reason_code)        

def on_disconnect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Disconnected to MQTT Broker!")
    if reason_code > 0:
        print("Failed to disconnect, return code %d\n", reason_code)
        

def sysCall_init():
    """ Initialization function for the robot and Velodyne LIDAR """
    sim = require('sim')
    
    # Pegando o objeto do robô completo
    self.pioneer = sim.getObject('.')
    # Pegando os motores
    self.motorLeft = sim.getObject("../leftMotor")
    self.motorRight = sim.getObject("../rightMotor")

    # Configurando MQTT
    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, CLIENT_NAME)
    self.client.on_connect = on_connect
    self.client.on_disconnect = on_disconnect

    # Pegando das variáveis globais
    broker = sim.getStringSignal("mqtt_broker")
    port = sim.getInt32Signal("mqtt_port")

    self.client.connect(broker, port)
    self.client.loop(0.01)  # Para processar callbacks


def sysCall_sensing():
    """ Publica dados da IMU, odometria e LIDAR via MQTT """
    sim = require('sim')

    # Captura os dados da IMU
    linear_velocity, angular_velocity = sim.getObjectVelocity(self.pioneer)

    # Captura os dados da odometria
    position = sim.getObjectPosition(self.pioneer, -1)
    orientation = sim.getObjectQuaternion(self.pioneer, -1)
    left_wheel_velocity = sim.getJointVelocity(self.motorLeft)
    right_wheel_velocity = sim.getJointVelocity(self.motorRight)

    # Publica no MQTT
    self.client.publish(f"{CLIENT_NAME}/imu/linearVelocity", str(linear_velocity))
    self.client.publish(f"{CLIENT_NAME}/imu/angularVelocity", str(angular_velocity))
    self.client.publish(f"{CLIENT_NAME}/odometry/pose", str(position + orientation))
    self.client.publish(f"{CLIENT_NAME}/odometry/wheel_vel", str([left_wheel_velocity, right_wheel_velocity]))
    
    


def sysCall_cleanup():
    # Clean disconnect of MQTT client
    self.client.disconnect()