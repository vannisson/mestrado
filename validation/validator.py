from collections import deque
import sys
sys.path.append("C:\\Users\\geova\\repos\\mestrado")

import os
import csv
import logging
import atexit
import numpy as np
from datetime import datetime
from paho.mqtt import client as mqtt

from config.variables import VALIDATION_TOPICS, BROKER, PORT
from proto.sensor_data_struct_pb2 import IMUData, OdometryData, LidarScan

# Importa agora as três variantes de DTW:
from validation.metrics import (
    compute_mse,
    compute_mae,
    compute_mape,
    compute_dtw,                  # DTW “cru” (soma acumulada)
    compute_dtw_and_path_length,  # retorna (dtw_total, path_len)
    compute_dtw_normalized        # DTW médio por passo
)

REFERENCE = "digital_twin"
TEST = "agv"

latest = {REFERENCE: {}, TEST: {}}
first_scan = {REFERENCE: False, TEST: False}
lidar_params = {REFERENCE: None, TEST: None}
params_checked = False
log_files = {}

# Buffers deslizantes, um para cada tópico/sufixo
refBuffers = {}
testBuffers = {}

# --- Logging setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# log_dir = os.path.join(os.getcwd(), "../logs", "validation")
log_dir = os.path.join(os.getcwd(), "logs", "validation")
os.makedirs(log_dir, exist_ok=True)

# --- MQTT callbacks ---
def on_connect(client, _, __, rc, ___):
    if rc == 0:
        logging.info("Connected to MQTT.")
        for topic in VALIDATION_TOPICS:
            for who in [REFERENCE, TEST]:
                full = topic.replace("CLIENT", who)
                client.subscribe(full)
                logging.info(f"Subscribed: {full}")
    else:
        logging.error(f"Failed to connect. Code: {rc}")

def on_message(client, _, msg):
    global params_checked
    topic = msg.topic
    who = REFERENCE if topic.startswith(REFERENCE) else TEST if topic.startswith(TEST) else None
    if not who:
        return

    suffix = topic.split("/", 1)[1]
    try:
        if "imu/linearVelocity" in suffix:
            latest[who][suffix] = list(IMUData().FromString(msg.payload).linear_velocity)
        elif "imu/angularVelocity" in suffix:
            latest[who][suffix] = list(IMUData().FromString(msg.payload).angular_velocity)
        elif "odometry/pose" in suffix:
            latest[who][suffix] = list(OdometryData().FromString(msg.payload).pose)
        elif "odometry/wheel_vel" in suffix:
            latest[who][suffix] = list(OdometryData().FromString(msg.payload).wheel_velocities)
        elif "sensor/ranges" in suffix:
            scan = LidarScan()
            scan.ParseFromString(msg.payload)
            latest[who]["sensor/ranges"] = list(scan.ranges)
            latest[who]["sensor/intensities"] = list(scan.intensities)

            if not first_scan[who]:
                lidar_params[who] = {
                    "angle_min": scan.angle_min,
                    "angle_max": scan.angle_max,
                    "angle_increment": scan.angle_increment,
                    "range_min": scan.range_min,
                    "range_max": scan.range_max,
                }
                first_scan[who] = True

            if all(first_scan.values()) and not params_checked:
                for key in lidar_params[REFERENCE]:
                    v1 = lidar_params[REFERENCE][key]
                    v2 = lidar_params[TEST][key]
                    if abs(v1 - v2) > 1e-6:
                        logging.warning(f"Lidar param diff ({key}): {v1} vs {v2}")
                params_checked = True
        else:
            logging.warning(f"Unknown topic: {suffix}")
            return
    except Exception as e:
        logging.error(f"Error parsing {suffix}: {e}")
        return

    compare_data(suffix)

def compare_data(suffix):
    if suffix not in latest[REFERENCE] or suffix not in latest[TEST]:
        return

    ref = latest[REFERENCE][suffix]
    test = latest[TEST][suffix]

    # Inicializa buffers para esse tópico se ainda não existirem
    if suffix not in refBuffers:
        refBuffers[suffix] = deque(maxlen=100)
        testBuffers[suffix] = deque(maxlen=100)

    # Adiciona a nova amostra ao buffer deslizante
    refBuffers[suffix].append(ref)
    testBuffers[suffix].append(test)

    # Cálculo ponto a ponto
    mse  = compute_mse(ref, test)
    rmse = np.sqrt(mse)
    mae  = compute_mae(ref, test)
    mape = compute_mape(ref, test)

    # Prepara as janelas (listas) para DTW
    window_ref  = list(refBuffers[suffix])
    window_test = list(testBuffers[suffix])

    # 1) DTW cru (custo total acumulado)
    dtw_cru = compute_dtw(window_ref, window_test)

    # 2) DTW normalizado (média de custo por passo)
    dtw_medio = compute_dtw_normalized(window_ref, window_test)

    logging.info(
        f"[{suffix}] "
        f"MSE={mse:.5f} | RMSE={rmse:.5f} | MAE={mae:.5f} | MAPE={mape:.2f}% "
        f"| DTW_cru={dtw_cru:.5f} | DTW_medio={dtw_medio:.5f}"
    )
    write_csv(suffix, ref, test, mse, rmse, mae, mape, dtw_cru, dtw_medio)

def write_csv(suffix, ref, test, mse, rmse, mae, mape, dtw_cru, dtw_medio):
    ts = datetime.now().isoformat()
    path = os.path.join(log_dir, suffix.replace("/", "_") + ".csv")

    if suffix not in log_files:
        first = not os.path.isfile(path)
        f = open(path, "a", newline="")
        w = csv.writer(f)
        log_files[suffix] = (f, w)
        if first:
            # Cabeçalho agora inclui DTW_cru e DTW_medio
            w.writerow([
                "timestamp", "mse", "rmse", "mae", "mape",
                "dtw_cru", "dtw_medio"
            ] + [f"ref_{i}" for i in range(len(ref))]
              + [f"test_{i}" for i in range(len(test))])
    _, writer = log_files[suffix]
    writer.writerow([ts, mse, rmse, mae, mape, dtw_cru, dtw_medio] + ref + test)

def close_all():
    for f, _ in log_files.values():
        f.close()

atexit.register(close_all)

# --- Main ---
if __name__ == "__main__":
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "validator")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT)
    client.loop_forever()
