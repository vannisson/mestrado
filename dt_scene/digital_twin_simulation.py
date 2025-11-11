# digital_twin_simulation.py
# Child Script (Python) para o Gêmeo Digital
# - Assina fleet_manager/target_position (TargetPosition)
# - Aplica a MESMA lei de controle (sem injetar pose!)
# - Publica IMU, Odometria (pose=x,y,z,qx,qy,qz,qw) e velocidades de roda
# - Loga CSVs no diretório do cenário corrente (definido pelo orchestrador)

import sys
sys.path.append("C:\\Users\\geova\\repos\\mestrado")

import os
import csv
import math
import time
import random
from datetime import datetime

from paho.mqtt import client as mqtt
from proto.sensor_data_struct_pb2 import OdometryData, IMUData
from proto.target_position_pb2 import TargetPosition
from config.variables import BROKER, PORT

# ----------------------------------------------------------------------------- #
# Estado e logs
# ----------------------------------------------------------------------------- #
self = type('', (), {})()

# ----------------------------------------------------------------------------- #
# Funções auxiliares de tempo e log
# ----------------------------------------------------------------------------- #
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
    """Escreve uma linha de log (reutiliza o handle se já aberto)."""
    if file_path not in _log_handles:
        _log_handles[file_path] = _ensure_log(file_path, headers)
    _, w = _log_handles[file_path]
    w.writerow(row)

def _update_pending_targets():
    now = time.time()
    ready = [item for item in self._pending_targets if item[0] <= now]
    if ready:
        # pega o mais recente disponível
        _, latest = max(ready, key=lambda it: it[0])
        self.target_position = latest
        # remove todos os já usados
        self._pending_targets[:] = [it for it in self._pending_targets if it[0] > now]
        
# ----------------------------------------------------------------------------- #
# Parâmetros do robô
# ----------------------------------------------------------------------------- #
WHEEL_RADIUS = 0.05
WHEEL_BASE   = 0.30
MQTT_QOS     = 1

COMM_DELAY_MEAN = 2.0   # atraso médio (s) -> mude para 0, 0.5, 1.0, 2.0
COMM_DELAY_STD  = 0.2   # jitter (s)

self._pending_targets = []  # fila de (t_exec, TargetPosition)
self.target_position  = None

# ----------------------------------------------------------------------------- #
# Utilitários
# ----------------------------------------------------------------------------- #
def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle

def mqtt_publish_ts(client, topic: str, payload: bytes | str):
    """Publica payload binário (protobuf) com QoS=1."""
    pub_ts_ms = int(time.time() * 1000)
    client.publish(topic, payload, qos=MQTT_QOS)
    return pub_ts_ms

# ----------------------------------------------------------------------------- #
# MQTT callbacks
# ----------------------------------------------------------------------------- #
def on_connect(client, userdata, flags, reason_code, properties):
    sim = require('sim')
    if reason_code == 0:
        sim.addLog(sim.verbosity_scriptinfos, "Twin: Conectado ao MQTT.")
        client.subscribe("fleet_manager/target_position", qos=MQTT_QOS)
    else:
        sim.addLog(sim.verbosity_errors, f"Twin: Falha na conexão (código {reason_code}).")

def on_disconnect(client, userdata, flags, reason_code, properties):
    sim = require('sim')
    if reason_code == 0:
        sim.addLog(sim.verbosity_scriptinfos, "Twin: Desconectado do MQTT.")
    else:
        sim.addLog(sim.verbosity_errors, f"Twin: Desconectado com erro (código {reason_code}).")

def on_message(client, userdata, msg):
    sim = require('sim')
    if msg.topic == "fleet_manager/target_position":
        target = TargetPosition()
        target.ParseFromString(msg.payload)

        # agenda com atraso
        delay = max(0.0, random.gauss(COMM_DELAY_MEAN, COMM_DELAY_STD))
        t_exec = time.time() + delay
        self._pending_targets.append((t_exec, target))

        sim.addLog(sim.verbosity_scriptinfos,
                   f"Twin: Target agendado para +{delay:.3f}s "
                   f"(x={target.x:.3f}, y={target.y:.3f}, θ={target.theta:.3f})")

# ----------------------------------------------------------------------------- #
# CoppeliaSim sysCalls
# ----------------------------------------------------------------------------- #
def sysCall_init():
    sim = require('sim')

    # --- Diretório base do cenário (lido do orchestrador) ---
    project_root = "C:\\Users\\geova\\repos\\mestrado"
    try:
        current_run_file = os.path.join(project_root, "logs", "experiments", "current_run.txt")
        if os.path.exists(current_run_file):
            with open(current_run_file, "r", encoding="utf-8") as f:
                base_dir = f.read().strip()
        else:
            base_dir = os.path.join(project_root, "logs", "experiments", "manual_run")
        self.log_dir = os.path.join(base_dir, "twin_logs")
    except Exception as e:
        self.log_dir = os.path.join(project_root, "logs", "twin_logs_fallback")
        print(f"[WARN] Falha ao obter caminho do cenário: {e}")

    os.makedirs(self.log_dir, exist_ok=True)
    sim.addLog(sim.verbosity_scriptinfos, f"[TWIN] Salvando logs em: {self.log_dir}")

    # Identidade e handles
    self.client_name = "digital_twin"
    self.pioneer    = sim.getObject('.')
    self.motorLeft  = sim.getObject("../leftMotor")
    self.motorRight = sim.getObject("../rightMotor")
    self.target_position = None

    # MQTT
    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, self.client_name)
    self.client.on_connect    = on_connect
    self.client.on_disconnect = on_disconnect
    self.client.on_message    = on_message
    self.client.connect(BROKER, PORT)
    self.client.loop_start()

# ----------------------------------------------------------------------------- #
# Controle do robô (lei de movimento igual ao AGV)
# ----------------------------------------------------------------------------- #
def sysCall_actuation():
    sim = require('sim')
    self.client.loop(0.01)

    _update_pending_targets()

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

# ----------------------------------------------------------------------------- #
# Sensoriamento e logs
# ----------------------------------------------------------------------------- #
def sysCall_sensing():
    sim = require('sim')

    linear_velocity, angular_velocity = sim.getObjectVelocity(self.pioneer)
    position    = sim.getObjectPosition(self.pioneer, -1)
    orientation = sim.getObjectQuaternion(self.pioneer, -1)
    euler       = sim.getObjectOrientation(self.pioneer, -1)
    theta       = euler[2]
    left_w      = sim.getJointVelocity(self.motorLeft)
    right_w     = sim.getJointVelocity(self.motorRight)

    # --- Publica IMU ---
    imu = IMUData(
        linear_velocity=list(linear_velocity),
        angular_velocity=list(angular_velocity),
    )
    mqtt_publish_ts(self.client, f"{self.client_name}/imu/linearVelocity", imu.SerializeToString())
    mqtt_publish_ts(self.client, f"{self.client_name}/imu/angularVelocity", imu.SerializeToString())

    # --- Publica Odometria ---
    odom = OdometryData(
        pose=list(position + orientation),
        wheel_velocities=[left_w, right_w],
    )
    mqtt_publish_ts(self.client, f"{self.client_name}/odometry/pose", odom.SerializeToString())
    mqtt_publish_ts(self.client, f"{self.client_name}/odometry/wheel_vel", odom.SerializeToString())

    # --- Logs CSV ---
    t = now_t()
    log_row(os.path.join(self.log_dir, "odom.csv"), ["t", "x", "y", "theta"], [t, position[0], position[1], theta])
    log_row(os.path.join(self.log_dir, "wheels.csv"), ["t", "wl", "wr"], [t, left_w, right_w])
    gx, gy, gz = angular_velocity
    log_row(os.path.join(self.log_dir, "imu.csv"), ["t", "ax", "ay", "az", "gx", "gy", "gz"], [t, 0.0, 0.0, 0.0, gx, gy, gz])

# ----------------------------------------------------------------------------- #
# Encerramento
# ----------------------------------------------------------------------------- #
def sysCall_cleanup():
    for f, _ in _log_handles.values():
        try: f.close()
        except: pass
    try:
        self.client.disconnect()
    except:
        pass
