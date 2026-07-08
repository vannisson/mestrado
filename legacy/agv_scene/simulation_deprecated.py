import sys
sys.path.append("C:\\Users\\geova\\repos\\mestrado") 
import os
import csv
from datetime import datetime
import math
import json
from paho.mqtt import client as mqtt
import proto.sensor_data_struct_pb2
from proto.twist_pb2 import Twist
from config.variables import VALIDATION_TOPICS, CONTROL_TOPIC, BROKER, PORT

self = type('', (), {})()

log_dir = os.path.join(os.getcwd(), "../logs", "agv_logs")
os.makedirs(log_dir, exist_ok=True)
log_files = {}

def sysCall_init():
    sim = require('sim')

    self.client_name = sim.getStringSignal("client_name")

    self.pioneer = sim.getObject('.')
    self.hokuyo = sim.getObject("../Hokuyo") 
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
    self.client.loop(0.01)

def sysCall_sensing():
    sim = require('sim')

    linear_velocity, angular_velocity = sim.getObjectVelocity(self.pioneer)
    position = sim.getObjectPosition(self.pioneer, -1)
    orientation = sim.getObjectQuaternion(self.pioneer, -1)
    left_wheel_velocity = sim.getJointVelocity(self.motorLeft)
    right_wheel_velocity = sim.getJointVelocity(self.motorRight)

    imu_msg = proto.sensor_data_struct_pb2.IMUData(
        linear_velocity=list(linear_velocity),
        angular_velocity=list(angular_velocity),
    )
    self.client.publish(f"{self.client_name}/imu/linearVelocity", imu_msg.SerializeToString())
    self.client.publish(f"{self.client_name}/imu/angularVelocity", imu_msg.SerializeToString())

    odom_msg = proto.sensor_data_struct_pb2.OdometryData(
        pose=list(position + orientation),
        wheel_velocities=[left_wheel_velocity, right_wheel_velocity],
    )
    self.client.publish(f"{self.client_name}/odometry/pose", odom_msg.SerializeToString())
    self.client.publish(f"{self.client_name}/odometry/wheel_vel", odom_msg.SerializeToString())

    log_data("imu/linearVelocity", linear_velocity)
    log_data("imu/angularVelocity", angular_velocity)
    log_data("odometry/pose", position + orientation)
    log_data("odometry/wheel_vel", [left_wheel_velocity, right_wheel_velocity])

    data_string = sim.readCustomDataBlock(self.hokuyo, 'LIDAR_SCAN')
    if data_string:
        ranges = sim.unpackFloatTable(data_string)
        num_points = len(ranges)
        
        scanning_angle = math.radians(360)
        angle_start = -scanning_angle / 2
        angle_increment = scanning_angle / num_points if num_points > 0 else 0
        max_dist = 6.0

        lidar_msg = proto.sensor_data_struct_pb2.LidarScan(
            angle_min=angle_start,
            angle_max=angle_start + scanning_angle,
            angle_increment=angle_increment,
            time_increment=0.0,
            scan_time=0.0,
            range_min=0.0,
            range_max=max_dist,
            ranges=ranges,
            intensities=[1.0 if r < max_dist else 0.0 for r in ranges],
        )

        self.client.publish(f"{self.client_name}/sensor/ranges", lidar_msg.SerializeToString())

        log_data("sensor/ranges", ranges)

    
def sysCall_actuation():
    sim = require('sim')

    self.client.loop(0.01)

    wheel_radius = 0.05
    wheel_base = 0.3

    v = self.cmd_linear_x
    w = self.cmd_angular_z

    left_velocity = (v - w * wheel_base / 2) / wheel_radius
    right_velocity = (v + w * wheel_base / 2) / wheel_radius

    sim.setJointTargetVelocity(self.motorLeft, left_velocity)
    sim.setJointTargetVelocity(self.motorRight, right_velocity)

def sysCall_cleanup():
    for f, _ in log_files.values():
        f.close()
    self.client.disconnect()

def on_connect(client, userdata, flags, reason_code, properties):
    sim = require('sim')
    if reason_code == 0:
        sim.addLog(sim.verbosity_scriptinfos, "Connected to MQTT Broker.")
        client.subscribe(CONTROL_TOPIC)
        sim.addLog(sim.verbosity_scriptinfos, f"Subscribed to: {CONTROL_TOPIC}")
    else:
        sim.addLog(sim.verbosity_errors, f"Failed to connect. Code: {reason_code}")

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

def log_data(topic_suffix, values):
    now = datetime.now().isoformat()
    filename = os.path.join(log_dir, topic_suffix.replace("/", "_") + ".csv")

    if topic_suffix not in log_files:
        file_exists = os.path.isfile(filename)
        f = open(filename, 'a', newline='')
        writer = csv.writer(f)
        log_files[topic_suffix] = (f, writer)
        if not file_exists:
            writer.writerow(["timestamp"] + [f"v{i}" for i in range(len(values))])

    _, writer = log_files[topic_suffix]
    writer.writerow([now] + list(values))