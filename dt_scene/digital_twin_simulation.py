import sys
import time
sys.path.append("C:\\Users\\geova\\repos\\mestrado")

import os
from datetime import datetime
import math
import csv
from paho.mqtt import client as mqtt
from proto.sensor_data_struct_pb2 import OdometryData, IMUData
from config.variables import BROKER, PORT

self = type('', (), {})()

log_dir = os.path.join(os.getcwd(), "../logs", "twin_logs")
os.makedirs(log_dir, exist_ok=True)
log_files = {}

# atraso base (20 ms)
BASE_DELAY = 0.02

# época em que vamos forçar um delay grande: 
# por exemplo, a partir de t=10s até t=15s do início da simulação
FORCE_DELAY_START = 10.0  
FORCE_DELAY_END = 15.0    
# quanto vamos atrasar nesse período (500 ms)
FORCE_DELAY_VALUE = 0.5   

# armazena t_instante de início do script
start_time = time.time()

def sysCall_init():
    sim = require('sim')

    self.client_name = sim.getStringSignal("client_name")

    self.pioneer = sim.getObject('.')
    self.motorLeft = sim.getObject("../leftMotor")
    self.motorRight = sim.getObject("../rightMotor")

    self.received_left_vel = 0.0
    self.received_right_vel = 0.0

    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, self.client_name)
    self.client.on_connect = on_connect
    self.client.on_disconnect = on_disconnect
    self.client.on_message = on_message

    self.client.connect(BROKER, PORT)
    self.client.loop(0.01)

def sysCall_actuation():
    sim = require('sim')
    self.client.loop(0.01)

    sim.setJointTargetVelocity(self.motorLeft, self.received_left_vel)
    sim.setJointTargetVelocity(self.motorRight, self.received_right_vel)

def sysCall_sensing():
    sim = require('sim')

    linear_velocity, angular_velocity = sim.getObjectVelocity(self.pioneer)
    position = sim.getObjectPosition(self.pioneer, -1)
    orientation = sim.getObjectQuaternion(self.pioneer, -1)
    left_wheel_velocity = sim.getJointVelocity(self.motorLeft)
    right_wheel_velocity = sim.getJointVelocity(self.motorRight)

    imu_msg = IMUData(
        linear_velocity=list(linear_velocity),
        angular_velocity=list(angular_velocity),
    )
    self.client.publish(f"{self.client_name}/imu/linearVelocity", imu_msg.SerializeToString())
    self.client.publish(f"{self.client_name}/imu/angularVelocity", imu_msg.SerializeToString())

    odom_msg = OdometryData(
        pose=list(position + orientation),
        wheel_velocities=[left_wheel_velocity, right_wheel_velocity],
    )
    self.client.publish(f"{self.client_name}/odometry/pose", odom_msg.SerializeToString())
    self.client.publish(f"{self.client_name}/odometry/wheel_vel", odom_msg.SerializeToString())

    log_data("imu/linearVelocity", linear_velocity)
    log_data("imu/angularVelocity", angular_velocity)
    log_data("odometry/pose", position + orientation)
    log_data("odometry/wheel_vel", [left_wheel_velocity, right_wheel_velocity])

def sysCall_cleanup():
    for f, _ in log_files.values():
        f.close()
    self.client.disconnect()

def on_connect(client, userdata, flags, reason_code, properties):
    sim = require('sim')
    if reason_code == 0:
        sim.addLog(sim.verbosity_scriptinfos, "Gêmeo: Conectado ao broker MQTT.")
        client.subscribe("agv/odometry/wheel_vel")
        sim.addLog(sim.verbosity_scriptinfos, "Gêmeo: Subscrito a agv/odometry/wheel_vel")
    else:
        sim.addLog(sim.verbosity_errors, f"Gêmeo: Falha na conexão. Código: {reason_code}")

def on_disconnect(client, userdata, flags, reason_code, properties):
    sim = require('sim')
    sim.addLog(sim.verbosity_scriptinfos, f"Gêmeo: Desconectado. Código: {reason_code}")

def on_message(client, userdata, msg):
    sim = require('sim')
    
    # calcula quanto tempo se passou desde o início
    elapsed = time.time() - start_time

    # determina o atraso atual:
    # - se estivermos dentro do intervalo FORCE_DELAY_START..FORCE_DELAY_END ⇒ atraso grande
    # - caso contrário ⇒ atraso base
    if FORCE_DELAY_START <= elapsed <= FORCE_DELAY_END:
        current_delay = FORCE_DELAY_VALUE
    else:
        current_delay = BASE_DELAY
        
    if msg.topic == "agv/odometry/wheel_vel":
        # aguarda o delay antes de interpretar a mensagem
        time.sleep(current_delay) 

        odom = OdometryData()
        odom.ParseFromString(msg.payload)
        if len(odom.wheel_velocities) >= 2:
            self.received_left_vel = odom.wheel_velocities[0]
            self.received_right_vel = odom.wheel_velocities[1]
            sim.addLog(sim.verbosity_debug, 
                       f"Gêmeo (após {current_delay}s): vL={self.received_left_vel:.2f}, vR={self.received_right_vel:.2f}")

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
