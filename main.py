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
    simVision = require('simVision')

    self.pioneer = sim.getObject('.')

    self.motorLeft = sim.getObject("../leftMotor")
    self.motorRight = sim.getObject("../rightMotor")

    visionSensorHandles = [sim.getObject(f"../sensor[{i}]") for i in range(4)]
    self.ptCloud = sim.getObject("../ptCloud")

    frequency = 5
    options = 2 + 8
    pointSize = 2
    coloring_closeAndFarDistance = [1, 4]
    displayScaling = 0.999

    self.lidar_handle = simVision.createVelodyneVPL16(
        visionSensorHandles, frequency, options, pointSize, coloring_closeAndFarDistance, displayScaling, self.ptCloud
    )

    if self.lidar_handle is None:
        print("Erro: falha na inicializacao do Velodyne")

    # Configurando MQTT
    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, CLIENT_NAME)
    self.client.on_connect = on_connect
    self.client.on_disconnect = on_disconnect

    broker = sim.getStringSignal("mqtt_broker")
    port = sim.getInt32Signal("mqtt_port")

    self.client.connect(broker, port)
    self.client.loop(0.01)  # Para processar callbacks


def sysCall_sensing():
    """ Publica dados da IMU, odometria e LIDAR via MQTT """
    sim = require('sim')
    simVision = require('simVision')

    # Captura os dados da IMU
    linear_velocity = sim.getObjectVelocity(self.pioneer)[0:3]
    angular_velocity = sim.getObjectVelocity(self.pioneer)[3:6]

    # Captura os dados da odometria
    position = sim.getObjectPosition(self.pioneer, -1)
    orientation = sim.getObjectQuaternion(self.pioneer, -1)
    left_wheel_velocity = sim.getJointVelocity(self.motorLeft)
    right_wheel_velocity = sim.getJointVelocity(self.motorRight)

    # Captura os dados do Velodyne
    if self.lidar_handle:
        raw_data = simVision.handleVelodyneVPL16(self.lidar_handle + sim.handleflag_abscoords, sim.getSimulationTimeStep())

        distances = [math.sqrt(raw_data[i]**2 + raw_data[i+1]**2 + raw_data[i+2]**2)
                     for i in range(0, len(raw_data), 15)] if raw_data else []
    else:
        print("Erro: lidar_handle não está definido!")
        distances = []

    # Publica no MQTT
    self.client.publish(f"{CLIENT_NAME}/imu/linearVelocity", str(linear_velocity))
    self.client.publish(f"{CLIENT_NAME}/imu/angularVelocity", str(angular_velocity))
    self.client.publish(f"{CLIENT_NAME}/odometry/pose", str(position + orientation))
    self.client.publish(f"{CLIENT_NAME}/odometry/wheel_vel", str([left_wheel_velocity, right_wheel_velocity]))
    self.client.publish(f"{CLIENT_NAME}/sensor/ranges", str(distances))


def sysCall_cleanup():
    # Clean disconnect of MQTT client
    self.client.disconnect()