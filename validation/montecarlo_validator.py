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
    compute_dtw,
    compute_dtw_normalized,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# buffers de trajetória
buffers = {"ref": deque(), "test": deque()}
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

def on_message(client, userdata, msg):
    # só odometry/pose interessa
    if "odometry/pose" not in msg.topic:
        return
    od = OdometryData().FromString(msg.payload).pose
    who = "ref" if msg.topic.startswith("digital_twin") else "test"
    with lock:
        buffers[who].append(list(od))

def command_loop():
    """
    Espera linhas em stdin:
      reset   -> limpa buffers
      compute -> calcula e imprime CSV no stdout
    """
    for line in sys.stdin:
        cmd = line.strip().lower()
        if cmd == "reset":
            with lock:
                buffers["ref"].clear()
                buffers["test"].clear()
            print("RESET_DONE", flush=True)
        elif cmd == "compute":
            with lock:
                ref_traj = list(buffers["ref"])
                test_traj = list(buffers["test"])
            if not ref_traj or not test_traj:
                print("ERROR_NO_DATA", flush=True)
                continue
            # achata para as métricas ponto-a-ponto
            ref_flat = [v for pose in ref_traj for v in pose]
            test_flat = [v for pose in test_traj for v in pose]

            mse      = compute_mse(ref_flat, test_flat)
            rmse     = np.sqrt(mse)
            mae      = compute_mae(ref_flat, test_flat)
            mape     = compute_mape(ref_flat, test_flat)
            dtw_cru  = compute_dtw(ref_traj, test_traj)
            dtw_norm = compute_dtw_normalized(ref_traj, test_traj)

            # imprime uma linha CSV: mse,rmse,mae,mape,dtw_cru,dtw_norm
            print(f"{mse},{rmse},{mae},{mape},{dtw_cru},{dtw_norm}", flush=True)
        else:
            logging.warning(f"Comando desconhecido: {cmd}")

def main():
    # inicia MQTT
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "montecarlo_validator")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT)

    # thread que lê stdin
    t = threading.Thread(target=command_loop, daemon=True)
    t.start()

    # loop principal MQTT
    client.loop_forever()

if __name__ == "__main__":
    main()
