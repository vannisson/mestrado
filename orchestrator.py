import sys
import time
import subprocess
import signal
from pathlib import Path

from experiments import ExperimentManager

COPPELIA_ROOT = Path(r"C:\Program Files\CoppeliaRobotics\CoppeliaSimEdu")
COPPELIA_EXE  = COPPELIA_ROOT / "coppeliaSim.exe"

SCENARIOS = [
    {
        "name":           "cenario_montecarlo",
        "agv_scene":      "agv_scene/agv_scene.ttt",
        "dt_scene":       "dt_scene/digital_twin_scene.ttt",
        "controller":     "controller/send_target_position.py",
        "validator":      "validation/validator.py",
        "base_target":    (1.0, 2.0),
        "noise_std":      0.05,
        "n_runs":         10,
        "wait_time":      5.0,
        "validation_log": "logs/validation/odometry_pose.csv",
        "metric_columns": ["mse","rmse","mae","mape","dtw_cru","dtw_medio"],
        "scenario_csv":   "logs/experiments/cenario_montecarlo/metrics.csv",
        "startup_timeout":20.0,
    },
]

def launch_coppelia(scene_rel: str) -> subprocess.Popen:
    scene_path = Path(__file__).parent / scene_rel
    if not scene_path.exists():
        raise FileNotFoundError(f"Cena não encontrada: {scene_path}")

    cmd = [
        str(COPPELIA_EXE),
        "-h",     # headless, sem GUI
        "-s", "0",# inicia sim imediatamente e não para sozinho
        str(scene_path)
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(COPPELIA_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
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

def launch_python(script: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, script],
        cwd=str(Path(__file__).parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

def stop(proc: subprocess.Popen):
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

def run_scenario(cfg: dict):
    print(f"\n=== Executando {cfg['name']} ===")
    wd = Path(__file__).parent

    # 1) lança AGVSim
    agv = launch_coppelia(cfg["agv_scene"])
    print("Aguardando AGVSim…")
    wait_for_simulation(agv, cfg["startup_timeout"], "AGVSim")

    # 2) lança TwinSim
    twin = launch_coppelia(cfg["dt_scene"])
    print("Aguardando TwinSim…")
    wait_for_simulation(twin, cfg["startup_timeout"], "TwinSim")

    # 3) controla e valida
    ctrl = launch_python(str(wd / cfg["controller"]))
    time.sleep(1)
    val  = launch_python(str(wd / cfg["validator"]))
    time.sleep(1)

    # 4) executa o experimento
    exp = ExperimentManager(
        base_target     = cfg["base_target"],
        noise_std       = cfg["noise_std"],
        n_runs          = cfg["n_runs"],
        wait_time       = cfg["wait_time"],
        validation_log  = str(wd / cfg["validation_log"]),
        metric_columns  = cfg["metric_columns"],
        scenario_csv    = str(wd / cfg["scenario_csv"]),
    )
    exp.run()

    # 5) finaliza
    for proc,name in ((ctrl,"Controller"), (val,"Validator"), (agv,"AGVSim"), (twin,"TwinSim")):
        print(f"Encerrando {name}…")
        stop(proc)

if __name__=="__main__":
    for scen in SCENARIOS:
        try:
            run_scenario(scen)
        except Exception as e:
            print(f"Erro no cenário {scen['name']}: {e}")
            break
    else:
        print("\n=== Todos os cenários concluídos ===")
