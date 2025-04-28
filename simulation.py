import math
import json
from paho.mqtt import client as mqtt
import sensor_data_struct_pb2  # novo import para o protobuf gerado

from handlers.config import TOPICS

def sysCall_init():
    sim = require('sim')
    
    self.client_name = sim.getStringSignal("client_name")
    
    self.pioneer = sim.getObject('.')
    self.motorLeft = sim.getObject("../leftMotor")
    self.motorRight = sim.getObject("../rightMotor")
    
    self.laserHandle = sim.getObject("../laser")
    self.jointHandle = sim.getObject("../joint")

    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, self.client_name)
    self.client.on_connect = on_connect
    self.client.on_disconnect = on_disconnect

    broker = sim.getStringSignal("mqtt_broker")
    port = sim.getInt32Signal("mqtt_port")

    self.client.connect(broker, port)
    self.client.loop(0.01)

def sysCall_sensing():
    sim = require('sim')

    linear_velocity, angular_velocity = sim.getObjectVelocity(self.pioneer)
    position = sim.getObjectPosition(self.pioneer, -1)
    orientation = sim.getObjectQuaternion(self.pioneer, -1)
    left_wheel_velocity = sim.getJointVelocity(self.motorLeft)
    right_wheel_velocity = sim.getJointVelocity(self.motorRight)
    
    max_dist = 6.0
    scanning_angle = math.radians(360)
    num_points = 684
    angle_start = -scanning_angle / 2

    ranges = []
    intensities = []

    for i in range(num_points):
        angle = angle_start + i * (scanning_angle / num_points)
        sim.setJointPosition(self.jointHandle, angle)
        res, dist, point, _, _ = sim.handleProximitySensor(self.laserHandle)
        if res > 0:
            ranges.append(round(dist, 3))
            intensities.append(1.0)
        else:
            ranges.append(round(max_dist, 3))
            intensities.append(0.0)

    # IMU
    imu_msg = sensor_data_struct_pb2.IMUData(
        linear_velocity=list(linear_velocity),
        angular_velocity=list(angular_velocity),
    )
    self.client.publish(f"{self.client_name}/imu/linearVelocity", imu_msg.SerializeToString())
    self.client.publish(f"{self.client_name}/imu/angularVelocity", imu_msg.SerializeToString())

    # ODOMETRY
    odom_msg = sensor_data_struct_pb2.OdometryData(
        pose=list(position + orientation),
        wheel_velocities=[left_wheel_velocity, right_wheel_velocity],
    )
    self.client.publish(f"{self.client_name}/odometry/pose", odom_msg.SerializeToString())
    self.client.publish(f"{self.client_name}/odometry/wheel_vel", odom_msg.SerializeToString())

    # LIDAR
    lidar_msg = sensor_data_struct_pb2.LidarScan(
        angle_min=angle_start,
        angle_max=angle_start + scanning_angle,
        angle_increment=scanning_angle / num_points,
        time_increment=0.0,
        scan_time=0.0,
        range_min=0.0,
        range_max=max_dist,
        ranges=ranges,
        intensities=intensities,
    )
    self.client.publish(f"{self.client_name}/sensor/ranges", lidar_msg.SerializeToString())


def sysCall_cleanup():
    self.client.disconnect()

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker!")
        for topic in TOPICS:
            topic = topic.replace("CLIENT", self.client_name)
            client.subscribe(topic)
            print(f"Subscribed to: {topic}")
    else:
        print("Failed to connect, return code %d\n", reason_code)

def on_disconnect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Disconnected from MQTT Broker!")
    if reason_code > 0:
        print("Failed to disconnect, return code %d\n", reason_code)
