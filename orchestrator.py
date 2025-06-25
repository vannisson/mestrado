# orchestrator.py

import sys
import time
import subprocess
import csv
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from controller.send_target_position import send_target_position

# Ajuste para sua instalação do CoppeliaSim
COPPELIA_ROOT = Path(r"C:\Program Files\CoppeliaRobotics\CoppeliaSimEdu")
COPPELIA_EXE  = COPPELIA_ROOT / "coppeliaSim.exe"

SCENARIOS = [
    {
        "name":           "cenario_montecarlo",
        "agv_scene":      "agv_scene/agv_scene.ttt",
        "dt_scene":       "dt_scene/digital_twin_scene.ttt",
        "base_target":    (1.0, 2.0),
        "n_runs":         1000,
        "noise_std":      0.05,
        "wait_time":      10.0,
        "metrics":        ["mse","rmse","mae","mape","dtw_cru","dtw_medio"],
        "startup_timeout":20.0,
    },
]

def launch_coppelia(scene_rel: str):
    scene = Path(__file__).parent / scene_rel
    cmd = [str(COPPELIA_EXE), "-h", "-s", "0", str(scene)]
    return subprocess.Popen(
        cmd, cwd=str(COPPELIA_ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )

def wait_for_simulation(proc: subprocess.Popen, timeout: float, label: str):
    """
    Lê stdout e imprime cada linha (debug), até encontrar 'Simulation started.'
    """
    deadline = time.time() + timeout
    buffer = []
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = "".join(buffer[-10:])
            raise RuntimeError(f"{label} morreu ({proc.poll()}). Últimas linhas:\n{tail}")
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue
        buffer.append(line)
        # Aqui imprimimos tudo para debug:
        print(f"[{label}] {line.strip()}")
        if "simulator launched." in line:
            print(f"[{label}] cena carregada e sim iniciada.")
            return
    tail = "".join(buffer[-10:])
    raise TimeoutError(f"{label} não iniciou em {timeout}s.\nÚltimas linhas:\n{tail}")

def launch_validator():
    wd = Path(__file__).parent
    return subprocess.Popen(
        [sys.executable, str(wd/"validation"/"montecarlo_validator.py")],
        cwd=str(wd),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, bufsize=1
    )

def stop(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=5)
        except: proc.kill()

def run_scenario(cfg):
    wd = Path(__file__).parent
    procs = {}

    try:
        print(f"\n=== {cfg['name']} ===")
        # 1) AGVSim
        procs['agv'] = launch_coppelia(cfg["agv_scene"])
        wait_for_simulation(procs['agv'], cfg["startup_timeout"], "AGVSim")
        # 2) TwinSim
        procs['twin'] = launch_coppelia(cfg["dt_scene"])
        wait_for_simulation(procs['twin'], cfg["startup_timeout"], "TwinSim")
        # 3) Validator
        procs['val'] = launch_validator()

        # 4) Prepara CSV de saída
        out_dir = wd/"logs"/"experiments"/cfg["name"]
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = out_dir/"metrics.csv"
        with open(csv_path, "w", newline="") as f:
            csv.writer(f).writerow(["epoch"] + cfg["metrics"])

        # 5) Loop de Monte Carlo
        for epoch in range(1, cfg["n_runs"]+1):
            # reset
            procs['val'].stdin.write("reset\n"); procs['val'].stdin.flush()
            _ = procs['val'].stdout.readline()

            # envia target
            dx, dy = np.random.normal(0, cfg["noise_std"], size=2)
            xt = cfg["base_target"][0] + dx
            yt = cfg["base_target"][1] + dy
            send_target_position(xt, yt)
            print(f"> [Epoch {epoch}] x={xt:.3f}, y={yt:.3f}")

            time.sleep(cfg["wait_time"])

            # compute com retry para evitar NO_DATA
            line = ""
            for attempt in range(5):
                procs['val'].stdin.write("compute\n"); procs['val'].stdin.flush()
                line = procs['val'].stdout.readline().strip()
                if line == "ERROR_NO_DATA":
                    print(f"[Epoch {epoch}] sem dados, retry {attempt+1}/5")
                    time.sleep(0.5)
                    continue
                break

            if line == "ERROR_NO_DATA":
                raise RuntimeError("Validator retornou ERROR_NO_DATA após 5 tentativas")
            if line.startswith("ERROR"):
                raise RuntimeError(line)

            vals = line.split(",")
            if len(vals) != len(cfg["metrics"]):
                raise RuntimeError(f"{len(vals)} métricas retornadas, esperado {len(cfg['metrics'])}")

            # grava no CSV
            with open(csv_path, "a", newline="") as f:
                csv.writer(f).writerow([epoch] + vals)

            print("   →", dict(zip(cfg["metrics"], vals)))

        # 6) Gera histogramas
        df = pd.read_csv(csv_path)
        for m in cfg["metrics"]:
            plt.figure(figsize=(6,4))
            df[m].hist(bins=30, edgecolor="black")
            plt.title(f"{m} ({cfg['name']})")
            plt.xlabel(m); plt.ylabel("Frequência")
            plt.grid(True, linestyle="--", alpha=0.5)
            png = out_dir/f"{m}_hist.png"
            plt.tight_layout(); plt.savefig(png); plt.close()
            print(f"Histograma salvo: {png.name}")

    finally:
        # 7) cleanup
        for name,p in procs.items():
            print(f"Encerrando {name}…")
            stop(p)

def main():
    for scen in SCENARIOS:
        try:
            run_scenario(scen)
        except Exception as e:
            print(f"Erro em {scen['name']}: {e}")
            break
    else:
        print("\n=== Todos os cenários concluídos ===")

if __name__=="__main__":
    main()
