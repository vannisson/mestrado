# montecarlo_validator.py
import sys
sys.path.append("C:\\Users\\geova\\repos\\mestrado")

import threading
import logging
import time
from collections import deque

import numpy as np
from paho.mqtt import client as mqtt

from config.variables import VALIDATION_TOPICS, BROKER, PORT
from proto.sensor_data_struct_pb2 import OdometryData
from validation.metrics import (
    compute_mse,
    compute_mae,
    compute_mape,
    compute_dtw,                 # DTW ND (já é alias)
    compute_dtw_normalized,      # DTW ND normalizado
    pearson_corr,
    discrete_frechet_distance,
    edr_distance,
    lag_ms,                      # lag_xcorr_ms em ms
)

FS_HZ = 20.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

buffers = {
    "ref": deque(maxlen=100000),   # AGV real/fonte
    "test": deque(maxlen=100000),  # digital twin
}
lock = threading.Lock()

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info("Conectado ao MQTT")
        for topic in VALIDATION_TOPICS:
            for who in ("digital_twin", "agv"):
                full = topic.replace("CLIENT", who)
                client.subscribe(full)
                logging.info(f"Subscribed: {full}")
    else:
        logging.error(f"Falha na conexão MQTT: {rc}")

def _topic_owner(topic: str) -> str:
    # 'ref' = agv (fonte); 'test' = digital_twin
    if topic.startswith("agv"):
        return "ref"
    if topic.startswith("digital_twin"):
        return "test"
    return "test"

def on_message(client, userdata, msg):
    try:
        topic = msg.topic or ""
        if "odometry/pose" not in topic:
            return

        who = _topic_owner(topic)

        od = OdometryData()
        od.ParseFromString(msg.payload)
        pose = list(od.pose)  # agora decodifica corretamente

        with lock:
            buffers[who].append(pose)

    except Exception as e:
        logging.warning(f"Falha ao processar msg em '{msg.topic}': {e}")

def command_loop():
    for line in sys.stdin:
        cmd = (line or "").strip().lower()
        if cmd == "reset":
            with lock:
                buffers["ref"].clear()
                buffers["test"].clear()
            print("RESET_DONE", flush=True)

        elif cmd == "stats":
            with lock:
                n_ref = len(buffers["ref"])
                n_test = len(buffers["test"])
            print(f"STATS {n_ref} {n_test}", flush=True)

        elif cmd == "compute":
            with lock:
                ref_traj = list(buffers["ref"])   # [[pose...], ...]
                test_traj = list(buffers["test"])

            if not ref_traj or not test_traj:
                print("ERROR_NO_DATA", flush=True)
                continue

            # --------- Métricas ponto-a-ponto (flatten) ---------
            ref_flat = np.array([v for pose in ref_traj for v in pose], dtype=float)
            test_flat = np.array([v for pose in test_traj for v in pose], dtype=float)

            min_len = min(ref_flat.size, test_flat.size)
            if min_len == 0:
                print("ERROR_NO_DATA", flush=True)
                continue
            if ref_flat.size != test_flat.size:
                ref_flat  = ref_flat[:min_len]
                test_flat = test_flat[:min_len]

            mse_val  = compute_mse(ref_flat, test_flat)
            rmse_val = float(np.sqrt(mse_val))
            mae_val  = compute_mae(ref_flat, test_flat)
            mape_val = compute_mape(ref_flat, test_flat)

            # --------- Trajetórias em matriz (N x D) -------------
            A = np.asarray(ref_traj, dtype=float)
            B = np.asarray(test_traj, dtype=float)
            if A.ndim == 1: A = A[:, None]
            if B.ndim == 1: B = B[:, None]

            # usa só XY para métricas geométricas
            A_xy = A[:, :2]
            B_xy = B[:, :2]

            # --------- DTW multivariado (XY) ----------------------
            dtw_cru  = compute_dtw(A_xy, B_xy, window=None)
            dtw_norm = compute_dtw_normalized(A_xy, B_xy, window=None)

            # --------- Distância de Fréchet (trajetória XY) -------
            frechet_xy = discrete_frechet_distance(A_xy, B_xy)

            # --------- EDR (x e y separados) ----------------------
            edr_x = edr_distance(A_xy[:, 0], B_xy[:, 0])
            edr_y = edr_distance(A_xy[:, 1], B_xy[:, 1])

            # --------- Correlação de Pearson (x, y) ---------------
            pearson_x = pearson_corr(A_xy[:, 0], B_xy[:, 0])
            pearson_y = pearson_corr(A_xy[:, 1], B_xy[:, 1])

            # --------- Lag temporal (x, y) ------------------------
            lag_x_ms = lag_ms(A_xy[:, 0], B_xy[:, 0], FS_HZ)
            lag_y_ms = lag_ms(A_xy[:, 1], B_xy[:, 1], FS_HZ)

            # ordem das colunas no CSV:
            # mse, rmse, mae, mape, dtw_cru, dtw_norm,
            # frechet_xy, edr_x, edr_y, pearson_x, pearson_y, lag_x_ms, lag_y_ms
            print(
                f"{mse_val},{rmse_val},{mae_val},{mape_val},"
                f"{dtw_cru},{dtw_norm},"
                f"{frechet_xy},{edr_x},{edr_y},"
                f"{pearson_x},{pearson_y},"
                f"{lag_x_ms},{lag_y_ms}",
                flush=True,
            )

        else:
            logging.warning(f"Comando desconhecido: {cmd}")

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "montecarlo_validator")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT)
    t = threading.Thread(target=command_loop, daemon=True)
    t.start()
    client.loop_forever()

if __name__ == "__main__":
    main()
