import math
import json
from paho.mqtt import client as mqtt
import data.sensor_data_struct_pb2
from data.twist_pb2 import Twist
from config import VALIDATION_TOPICS, CONTROL_TOPIC, BROKER, PORT

self = type('', (), {})()

def sysCall_init():
    sim = require('sim')

    self.client_name = sim.getStringSignal("client_name")

    self.pioneer = sim.getObject('.')
    self.motorLeft = sim.getObject("../leftMotor")
    self.motorRight = sim.getObject("../rightMotor")

    self.laserHandle = sim.getObject("../laser")
    self.jointHandle = sim.getObject("../joint")

    self.cmd_linear_x = 0.0
    self.cmd_angular_z = 0.0

    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, self.client_name)
    self.client.on_connect = on_connect
    self.client.on_disconnect = on_disconnect
    self.client.on_message = on_message

    self.client.connect(BROKER, PORT)
    self.client.loop(0.01)  # Para garantir processamento de conexão

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

    imu_msg = data.sensor_data_struct_pb2.IMUData(
        linear_velocity=list(linear_velocity),
        angular_velocity=list(angular_velocity),
    )
    self.client.publish(f"{self.client_name}/imu/linearVelocity", imu_msg.SerializeToString())
    self.client.publish(f"{self.client_name}/imu/angularVelocity", imu_msg.SerializeToString())

    odom_msg = data.sensor_data_struct_pb2.OdometryData(
        pose=list(position + orientation),
        wheel_velocities=[left_wheel_velocity, right_wheel_velocity],
    )
    self.client.publish(f"{self.client_name}/odometry/pose", odom_msg.SerializeToString())
    self.client.publish(f"{self.client_name}/odometry/wheel_vel", odom_msg.SerializeToString())

    lidar_msg = data.sensor_data_struct_pb2.LidarScan(
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

def sysCall_actuation():
    sim = require('sim')

    self.client.loop(0.01)  # Processa mensagens MQTT na thread certa

    wheel_radius = 0.05
    wheel_base = 0.3

    v = self.cmd_linear_x
    w = self.cmd_angular_z

    left_velocity = (v - w * wheel_base / 2) / wheel_radius
    right_velocity = (v + w * wheel_base / 2) / wheel_radius

    sim.setJointTargetVelocity(self.motorLeft, left_velocity)
    sim.setJointTargetVelocity(self.motorRight, right_velocity)

def sysCall_cleanup():
    self.client.disconnect()

def on_connect(client, userdata, flags, reason_code, properties):
    sim = require('sim')

    if reason_code == 0:
        sim.addLog(sim.verbosity_scriptinfos, "Connected to MQTT Broker!")
        control_topic = CONTROL_TOPIC.replace("CLIENT", self.client_name)
        client.subscribe(control_topic)
        sim.addLog(sim.verbosity_scriptinfos, f"Subscribed to control topic: {control_topic}")
    else:
        sim.addLog(sim.verbosity_errors, f"Failed to connect, return code {reason_code}")

def on_disconnect(client, userdata, flags, reason_code, properties):
    sim = require('sim')

    if reason_code == 0:
        sim.addLog(sim.verbosity_scriptinfos, "Disconnected from MQTT Broker!")
    else:
        sim.addLog(sim.verbosity_errors, f"Failed to disconnect, return code {reason_code}")

def on_message(client, userdata, msg):
    sim = require('sim')

    if msg.topic.endswith("/cmd_vel"):
        twist_msg = Twist()
        twist_msg.ParseFromString(msg.payload)
        self.cmd_linear_x = twist_msg.linear_x
        self.cmd_angular_z = twist_msg.angular_z
        # sim.addLog(sim.verbosity_scriptinfos, f"Received cmd_vel -> linear_x: {self.cmd_linear_x}, angular_z: {self.cmd_angular_z}")
