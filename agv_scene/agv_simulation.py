import sys
sys.path.append("C:\\Users\\geova\\repos\\mestrado")

import os
import csv
from datetime import datetime
import math
import json
from paho.mqtt import client as mqtt
import proto.sensor_data_struct_pb2
from proto.target_position_pb2 import TargetPosition
from config.variables import VALIDATION_TOPICS, BROKER, PORT

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

    self.target_position = None

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

    if self.target_position is None:
        return

    wheel_radius = 0.05
    wheel_base = 0.3

    # posicao atual do robo
    position = sim.getObjectPosition(self.pioneer, -1)
    orientation = sim.getObjectOrientation(self.pioneer, -1)
    x, y = position[0], position[1]
    theta = orientation[2]

    # alvo
    dx = self.target_position.x - x
    dy = self.target_position.y - y
    
    # calcula a distancia entre o robo e o ponto
    distance = math.hypot(dx, dy)

    # se for abaixo de 0.1, assume que ja esta no lugar
    if distance < 0.1:
        left_velocity = 0.0
        right_velocity = 0.0
    else:
        target_theta = math.atan2(dy, dx)
        diff_theta = normalize_angle(target_theta - theta)

        linear_speed = 0.4 if abs(diff_theta) < 0.4 else 0.0
        angular_speed = max(-1.2, min(1.2, diff_theta))

        left_velocity = (linear_speed - angular_speed * wheel_base / 2) / wheel_radius
        right_velocity = (linear_speed + angular_speed * wheel_base / 2) / wheel_radius

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
        client.subscribe("fleet_manager/target_position")
        sim.addLog(sim.verbosity_scriptinfos, "Subscribed to: fleet_manager/target_position")
    else:
        sim.addLog(sim.verbosity_errors, f"Failed to connect. Code: {reason_code}")

def on_disconnect(client, userdata, flags, reason_code, properties):
    sim = require('sim')
    if reason_code == 0:
        sim.addLog(sim.verbosity_scriptinfos, "Disconnected from MQTT Broker.")
    else:
        sim.addLog(sim.verbosity_errors, f"Disconnected with error code: {reason_code}")

def on_message(client, userdata, msg):
    sim = require('sim')
    if msg.topic == "fleet_manager/target_position":
        target = TargetPosition()
        target.ParseFromString(msg.payload)
        self.target_position = target
        sim.addLog(sim.verbosity_scriptinfos, f"Target recebido: x={target.x}, y={target.y}, theta={target.theta}")

def normalize_angle(angle):
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle

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