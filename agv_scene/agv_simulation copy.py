# agv_simulation.py
# Child Script (Python) para o AGV (fonte)
# - Assina fleet_manager/target_position (TargetPosition)
# - Controla o Pioneer por perseguição a ponto (gera v,w -> wl,wr)
# - Publica IMU, Odometria (pose=pos+quat) e velocidades de roda
# - Loga CSVs em ../logs/agv_logs

import sys
sys.path.append("C:\\Users\\geova\\repos\\mestrado")

import os
import csv
from datetime import datetime
import math

from paho.mqtt import client as mqtt

import proto.sensor_data_struct_pb2
from proto.target_position_pb2 import TargetPosition
from config.variables import BROKER, PORT

# -----------------------------------------------------------------------------
# Estado "self" no estilo Coppelia (para manter compatibilidade com seu script)
# -----------------------------------------------------------------------------
self = type('', (), {})()

# Diretório de logs
log_dir = os.path.join(os.getcwd(), "../logs", "agv_logs")
os.makedirs(log_dir, exist_ok=True)
log_files = {}

# Parâmetros do robô (use os que já estavam funcionando na sua cena)
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
        sim.addLog(sim.verbosity_scriptinfos, "AGV: Conectado ao MQTT.")
        client.subscribe("fleet_manager/target_position")
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
    
    sim.addLog(sim.verbosity_scriptinfos, f"AGV: Recebi uma mensagem.")

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

    # Handles (mesma estrutura que você usava)
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
    # Usaremos loop curto em cada passo (como no seu script antigo)
    # Alternativamente, poderia ser loop_start/loop_stop no init/cleanup.

def sysCall_sensing():
    sim = require('sim')

    # Telemetria do robô
    linear_velocity, angular_velocity = sim.getObjectVelocity(self.pioneer)  # vetores 3D
    position    = sim.getObjectPosition(self.pioneer, -1)                    # [x,y,z]
    orientation = sim.getObjectQuaternion(self.pioneer, -1)                  # [qx,qy,qz,qw]
    left_w      = sim.getJointVelocity(self.motorLeft)
    right_w     = sim.getJointVelocity(self.motorRight)

    # Publica IMU (linear+angular velocity)
    imu_msg = proto.sensor_data_struct_pb2.IMUData(
        linear_velocity=list(linear_velocity),
        angular_velocity=list(angular_velocity),
    )
    self.client.publish(f"{self.client_name}/imu/linearVelocity", imu_msg.SerializeToString())
    self.client.publish(f"{self.client_name}/imu/angularVelocity", imu_msg.SerializeToString())

    # Publica Odometria (pose = pos + quat) e rodas
    odom_msg = proto.sensor_data_struct_pb2.OdometryData(
        pose=list(position + orientation),
        wheel_velocities=[left_w, right_w],
    )
    self.client.publish(f"{self.client_name}/odometry/pose", odom_msg.SerializeToString())
    self.client.publish(f"{self.client_name}/odometry/wheel_vel", odom_msg.SerializeToString())

    # Log CSVs
    log_data("imu/linearVelocity",  linear_velocity)
    log_data("imu/angularVelocity", angular_velocity)
    log_data("odometry/pose",       position + orientation)
    log_data("odometry/wheel_vel",  [left_w, right_w])

    # Lidar (opcional) — mantém seu formato antigo
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

    # Integra o loop MQTT rapidamente
    self.client.loop(0.01)

    # Sem alvo? não anda
    if self.target_position is None:
        return

    # Pega pose atual (para calcular o controle)
    position    = sim.getObjectPosition(self.pioneer, -1)       # [x,y,z]
    orientation = sim.getObjectOrientation(self.pioneer, -1)    # [alpha,beta,gamma] (Euler ZYX)
    x, y = position[0], position[1]
    theta = orientation[2]

    # Alvo
    dx = self.target_position.x - x
    dy = self.target_position.y - y

    # Distância ao alvo
    distance = math.hypot(dx, dy)

    if distance < 0.1:
        left_velocity  = 0.0
        right_velocity = 0.0
    else:
        target_theta = math.atan2(dy, dx)
        diff_theta = normalize_angle(target_theta - theta)

        # Lei simples (como a sua): anda só quando o heading está “ok”
        linear_speed  = 0.4 if abs(diff_theta) < 0.4 else 0.0
        angular_speed = max(-1.2, min(1.2, diff_theta))

        left_velocity  = (linear_speed - angular_speed * WHEEL_BASE / 2) / WHEEL_RADIUS
        right_velocity = (linear_speed + angular_speed * WHEEL_BASE / 2) / WHEEL_RADIUS

    sim.setJointTargetVelocity(self.motorLeft,  left_velocity)
    sim.setJointTargetVelocity(self.motorRight, right_velocity)

def sysCall_cleanup():
    # Fecha CSVs
    for f, _ in log_files.values():
        try: f.close()
        except: pass
    # Desconecta MQTT
    try:
        self.client.disconnect()
    except:
        pass
