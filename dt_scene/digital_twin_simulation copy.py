# digital_twin_simulation.py
# Child Script (Python) para o Gêmeo Digital
# - Assina fleet_manager/target_position (TargetPosition)
# - Aplica a MESMA lei de controle (sem injetar pose!)
# - Publica IMU, Odometria (pose=pos+quat) e velocidades de roda
# - Loga CSVs em ../logs/twin_logs

import sys
sys.path.append("C:\\Users\\geova\\repos\\mestrado")

import os
import csv
from datetime import datetime
import math

from paho.mqtt import client as mqtt

from proto.sensor_data_struct_pb2 import OdometryData, IMUData
from proto.target_position_pb2 import TargetPosition
from config.variables import BROKER, PORT

# -----------------------------------------------------------------------------
# Estado e logs
# -----------------------------------------------------------------------------
self = type('', (), {})()

log_dir = os.path.join(os.getcwd(), "../logs", "twin_logs")
os.makedirs(log_dir, exist_ok=True)
log_files = {}

# Parâmetros (iguais ao AGV)
WHEEL_RADIUS = 0.05
WHEEL_BASE   = 0.30

# -----------------------------------------------------------------------------
# Utilitários
# -----------------------------------------------------------------------------
def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle

def log_data(topic_suffix: str, values):
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

# -----------------------------------------------------------------------------
# Callbacks MQTT
# -----------------------------------------------------------------------------
def on_connect(client, userdata, flags, reason_code, properties):
    sim = require('sim')
    if reason_code == 0:
        sim.addLog(sim.verbosity_scriptinfos, "Twin: Conectado ao MQTT.")
        client.subscribe("fleet_manager/target_position")
        sim.addLog(sim.verbosity_scriptinfos, "Twin: Subscrito em fleet_manager/target_position")
    else:
        sim.addLog(sim.verbosity_errors, f"Twin: Falha na conexão. Código: {reason_code}")

def on_disconnect(client, userdata, reason_code, properties):
    sim = require('sim')
    sim.addLog(sim.verbosity_scriptinfos, f"Twin: Desconectado (cód {reason_code}).")

def on_message(client, userdata, msg):
    sim = require('sim')
    
    sim.addLog(sim.verbosity_scriptinfos, f"Twin: Recebi uma mensagem.")
    
    if msg.topic == "fleet_manager/target_position":
        target = TargetPosition()
        target.ParseFromString(msg.payload)
        self.target_position = target
        sim.addLog(sim.verbosity_scriptinfos,
                   f"Twin: Target recebido: x={target.x:.3f}, y={target.y:.3f}, theta={target.theta:.3f}")

# -----------------------------------------------------------------------------
# CoppeliaSim sysCalls
# -----------------------------------------------------------------------------
def sysCall_init():
    sim = require('sim')

    self.client_name = "digital_twin"

    self.pioneer    = sim.getObject('.')
    self.motorLeft  = sim.getObject("../leftMotor")
    self.motorRight = sim.getObject("../rightMotor")

    self.target_position = None

    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, self.client_name)
    self.client.on_connect    = on_connect
    self.client.on_disconnect = on_disconnect
    self.client.on_message    = on_message

    self.client.connect(BROKER, PORT)
    # Segue o mesmo padrão do AGV: loop curtinho por passo
    # (poderia usar loop_start/stop se preferir)

def sysCall_actuation():
    sim = require('sim')
    self.client.loop(0.01)

    if self.target_position is None:
        return

    position    = sim.getObjectPosition(self.pioneer, -1)
    orientation = sim.getObjectOrientation(self.pioneer, -1)
    x, y = position[0], position[1]
    theta = orientation[2]

    dx = self.target_position.x - x
    dy = self.target_position.y - y

    distance = math.hypot(dx, dy)

    if distance < 0.1:
        left_velocity  = 0.0
        right_velocity = 0.0
    else:
        target_theta = math.atan2(dy, dx)
        diff_theta = normalize_angle(target_theta - theta)

        linear_speed  = 0.4 if abs(diff_theta) < 0.4 else 0.0
        angular_speed = max(-1.2, min(1.2, diff_theta))

        left_velocity  = (linear_speed - angular_speed * WHEEL_BASE / 2) / WHEEL_RADIUS
        right_velocity = (linear_speed + angular_speed * WHEEL_BASE / 2) / WHEEL_RADIUS

    sim.setJointTargetVelocity(self.motorLeft,  left_velocity)
    sim.setJointTargetVelocity(self.motorRight, right_velocity)

def sysCall_sensing():
    sim = require('sim')

    linear_velocity, angular_velocity = sim.getObjectVelocity(self.pioneer)
    position    = sim.getObjectPosition(self.pioneer, -1)
    orientation = sim.getObjectQuaternion(self.pioneer, -1)
    left_w      = sim.getJointVelocity(self.motorLeft)
    right_w     = sim.getJointVelocity(self.motorRight)

    # IMU
    imu = IMUData(
        linear_velocity=list(linear_velocity),
        angular_velocity=list(angular_velocity),
    )
    self.client.publish(f"{self.client_name}/imu/linearVelocity", imu.SerializeToString())
    self.client.publish(f"{self.client_name}/imu/angularVelocity", imu.SerializeToString())

    # Odometria (pose = pos + quat) e rodas
    odom = OdometryData(
        pose=list(position + orientation),
        wheel_velocities=[left_w, right_w],
    )
    self.client.publish(f"{self.client_name}/odometry/pose", odom.SerializeToString())
    self.client.publish(f"{self.client_name}/odometry/wheel_vel", odom.SerializeToString())

    # Logs
    log_data("imu/linearVelocity",  linear_velocity)
    log_data("imu/angularVelocity", angular_velocity)
    log_data("odometry/pose",       position + orientation)
    log_data("odometry/wheel_vel",  [left_w, right_w])

def sysCall_cleanup():
    for f, _ in log_files.values():
        try: f.close()
        except: pass
    try:
        self.client.disconnect()
    except:
        pass
