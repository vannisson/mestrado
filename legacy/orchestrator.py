import sys
import time
import signal
import subprocess
from pathlib import Path

from experiment import ExperimentManager

# Ajuste para o seu executável do CoppeliaSim
COPPELIA = "coppeliaSim"

SCENARIOS = [
    {
        "name": "cenario_montecarlo",
        "agv_scene":  "agv_scene/agv_scene.ttt",
        "dt_scene":   "dt_scene/digital_twin_scene.ttt",
        "controller": "controller/send_target_position.py",
        "validator":  "validation/validator.py",
        # parâmetros do Monte Carlo
        "base_target":    (1.0, 2.0),
        "noise_std":      0.05,
        "n_runs":         1000,
        "wait_time":      5.0,
        # CSV gerado pelo validator que contém as métricas
        "metric_log":     "logs/validation/odometry_pose.csv",
        "metric_columns": ["mse","rmse","mae","mape","dtw_cru","dtw_medio"],
    },
    # … adicione aqui seus outros 2 cenários …
]

def launch_coppelia(scene_path: str):
    return subprocess.Popen(
        [COPPELIA, "-h", "-s", scene_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

def launch_python(script_path: str):
    return subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

def stop(proc: subprocess.Popen):
    try:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

def run_scenario(cfg: dict):
    print(f"\n=== Executando {cfg['name']} ===")
    workdir = Path(__file__).parent

    # diretório de saída dos histogramas
    out_dir = workdir / "logs" / "experiments" / cfg["name"]
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) inicia as duas cenas no CoppeliaSim em modo headless
    agv_proc = launch_coppelia(str(workdir / cfg["agv_scene"]))
    dt_proc  = launch_coppelia(str(workdir / cfg["dt_scene"]))
    time.sleep(10)  # espera carregar cenas e scripts internos

    # 2) inicia o controller de posição
    ctrl_proc = launch_python(str(workdir / cfg["controller"]))
    time.sleep(2)

    # 3) inicia o validator
    val_proc  = launch_python(str(workdir / cfg["validator"]))
    time.sleep(2)

    # 4) executa o Monte Carlo
    exp = ExperimentManager(
        base_target    = cfg["base_target"],
        noise_std      = cfg["noise_std"],
        n_runs         = cfg["n_runs"],
        wait_time      = cfg["wait_time"],
        metric_log     = str(workdir / cfg["metric_log"]),
        metric_columns = cfg["metric_columns"],
    )
    exp.run_monte_carlo()
    exp.save_all_histograms(out_dir=out_dir, bins=40)

    # 5) encerra todos os processos
    for p in (ctrl_proc, val_proc, agv_proc, dt_proc):
        stop(p)

if __name__ == "__main__":
    for scen in SCENARIOS:
        run_scenario(scen)
    print("\n=== Todos os cenários concluídos ===")
