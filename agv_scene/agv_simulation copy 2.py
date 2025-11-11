# agv_simulation.py
# Child Script (Python) para o AGV (fonte)
# - Assina fleet_manager/target_position (TargetPosition)
# - Controla o Pioneer por perseguição a ponto (gera v,w -> wl,wr)
# - Publica IMU, Odometria (pose=x,y,z,qx,qy,qz,qw) e velocidades de roda
# - Loga CSVs em ../logs/agv_logs

import sys
sys.path.append("C:\\Users\\geova\\repos\\mestrado")

import os
import csv
import math
import time
from datetime import datetime

from paho.mqtt import client as mqtt
import proto.sensor_data_struct_pb2
from proto.target_position_pb2 import TargetPosition
from config.variables import BROKER, PORT

# -----------------------------------------------------------------------------
# Estado "self" no estilo Coppelia (mantém compatibilidade com script)
# -----------------------------------------------------------------------------
self = type('', (), {})()

# Diretório de logs
log_dir = os.path.join(os.getcwd(), "../logs", "agv_logs")
os.makedirs(log_dir, exist_ok=True)

# Parâmetros do robô
WHEEL_RADIUS = 0.05
WHEEL_BASE   = 0.30
MQTT_QOS     = 1

# -----------------------------------------------------------------------------
# Tempo e logging padronizado (t, x, y, theta)
# -----------------------------------------------------------------------------
start_time = time.perf_counter()

def now_t():
    """Tempo relativo (segundos) desde o início da simulação"""
    return float(time.perf_counter() - start_time)

_log_handles = {}

def _ensure_log(path, headers):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    f = open(path, "a", newline="")
    w = csv.writer(f)
    if new:
        w.writerow(headers)
    return f, w

def log_row(file_path, headers, row):
    if file_path not in _log_handles:
        _log_handles[file_path] = _ensure_log(file_path, headers)
    _, w = _log_handles[file_path]
    w.writerow(row)

# -----------------------------------------------------------------------------
# Utilitários
# -----------------------------------------------------------------------------
def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle

def mqtt_publish_ts(client, topic: str, payload: bytes | str):
    """Publica payload binário (protobuf) com QoS=1 e timestamp opcional"""
    pub_ts_ms = int(time.time() * 1000)

    # Só anexa timestamp se for texto, nunca mexe em binário
    if isinstance(payload, str) and "\n" not in payload and "pub_ts_ms=" not in payload:
        payload = f"{payload};pub_ts_ms={pub_ts_ms}"

    client.publish(topic, payload, qos=MQTT_QOS)
    return pub_ts_ms

# -----------------------------------------------------------------------------
# Callbacks MQTT
# -----------------------------------------------------------------------------
def on_connect(client, userdata, flags, reason_code, properties):
    sim = require('sim')
    if reason_code == 0:
        sim.addLog(sim.verbosity_scriptinfos, "AGV: Conectado ao MQTT.")
        client.subscribe("fleet_manager/target_position", qos=MQTT_QOS)
        sim.addLog(sim.verbosity_scriptinfos, "AGV: Subscrito em fleet_manager/target_position")
    else:
        sim.addLog(sim.verbosity_errors, f"AGV: Falha na conexão. Código: {reason_code}")

def on_disconnect(client, userdata, flags, reason_code, properties):
    sim = require('sim')
    if reason_code == 0:
        sim.addLog(sim.verbosity_scriptinfos, "AGV: Desconectado do MQTT.")
    else:
        sim.addLog(sim.verbosity_errors, f"AGV: Desconectado com erro (código {reason_code}).")

def on_message(client, userdata, msg):
    sim = require('sim')
    sim.addLog(sim.verbosity_scriptinfos, f"MQTT msg recebida em {msg.topic} ({len(msg.payload)} bytes)")
    if msg.topic == "fleet_manager/target_position":
        target = TargetPosition()
        target.ParseFromString(msg.payload)
        self.target_position = target
        sim.addLog(sim.verbosity_scriptinfos,
                   f"AGV: Target recebido: x={target.x:.3f}, y={target.y:.3f}, theta={target.theta:.3f}")

# -----------------------------------------------------------------------------
# CoppeliaSim sysCalls
# -----------------------------------------------------------------------------
def sysCall_init():
    sim = require('sim')

    # Identidade (prefixo dos tópicos de telemetria)
    self.client_name = "agv"

    # Handles
    self.pioneer    = sim.getObject('.')
    self.hokuyo     = sim.getObject("../Hokuyo")
    self.motorLeft  = sim.getObject("../leftMotor")
    self.motorRight = sim.getObject("../rightMotor")

    # Estado
    self.target_position = None

    # MQTT
    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, self.client_name)
    self.client.on_connect = on_connect
    self.client.on_disconnect = on_disconnect
    self.client.on_message = on_message
    self.client.connect(BROKER, PORT)
    self.client.loop_start()

def sysCall_sensing():
    sim = require('sim')

    # Telemetria do robô
    linear_velocity, angular_velocity = sim.getObjectVelocity(self.pioneer)
    position    = sim.getObjectPosition(self.pioneer, -1)
    orientation = sim.getObjectQuaternion(self.pioneer, -1)  # quaternion completo
    euler       = sim.getObjectOrientation(self.pioneer, -1)
    theta       = euler[2]
    left_w      = sim.getJointVelocity(self.motorLeft)
    right_w     = sim.getJointVelocity(self.motorRight)

    # --- Publica IMU (linear + angular velocity)
    imu_msg = proto.sensor_data_struct_pb2.IMUData(
        linear_velocity=list(linear_velocity),
        angular_velocity=list(angular_velocity),
    )
    mqtt_publish_ts(self.client, f"{self.client_name}/imu/linearVelocity", imu_msg.SerializeToString())
    mqtt_publish_ts(self.client, f"{self.client_name}/imu/angularVelocity", imu_msg.SerializeToString())

    # --- Publica Odometria (pose = x,y,z,qx,qy,qz,qw) e velocidades das rodas
    odom_msg = proto.sensor_data_struct_pb2.OdometryData(
        pose=list(position + orientation),
        wheel_velocities=[left_w, right_w],
    )
    mqtt_publish_ts(self.client, f"{self.client_name}/odometry/pose", odom_msg.SerializeToString())
    mqtt_publish_ts(self.client, f"{self.client_name}/odometry/wheel_vel", odom_msg.SerializeToString())

    # --- Logs CSV padronizados ---
    t = now_t()

    # odom.csv
    log_row(os.path.join(log_dir, "odom.csv"),
            ["t", "x", "y", "theta"],
            [t, position[0], position[1], theta])

    # wheels.csv
    log_row(os.path.join(log_dir, "wheels.csv"),
            ["t", "wl", "wr"],
            [t, left_w, right_w])

    # imu.csv
    ax, ay, az = 0.0, 0.0, 0.0
    gx, gy, gz = angular_velocity
    log_row(os.path.join(log_dir, "imu.csv"),
            ["t", "ax", "ay", "az", "gx", "gy", "gz"],
            [t, ax, ay, az, gx, gy, gz])

    # --- Lidar (opcional) ---
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
        mqtt_publish_ts(self.client, f"{self.client_name}/sensor/ranges", lidar_msg.SerializeToString())

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

def sysCall_cleanup():
    for f, _ in _log_handles.values():
        try: f.close()
        except: pass
    try:
        self.client.disconnect()
    except:
        pass
