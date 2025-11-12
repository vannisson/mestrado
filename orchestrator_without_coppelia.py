# orchestrator_nocoppelia.py
# Monte Carlo de validação SEM iniciar o CoppeliaSim
# - Assume que as cenas (AGV + Gêmeo Digital + Fleet Manager) já estão abertas
# - Mantém estrutura e fluxo do orchestrator original
# - Lança apenas o validator, envia targets, coleta métricas e gera logs/resumo

import sys
import time
import subprocess
import csv
import json
import hashlib
from pathlib import Path
import argparse

import numpy as np
import pandas as pd

from controller.send_target_position import send_target_position

# -----------------------------------------------------------------------------
# Configurações básicas (idênticas, exceto sem COPPELIA_ROOT/EXE)
# -----------------------------------------------------------------------------
SCENARIOS = [
    {
        "name":           "cenario_montecarlo",
        "agv_scene":      "agv_scene/agv_scene.ttt",          # mantido só por compatibilidade / documentação
        "dt_scene":       "dt_scene/digital_twin_scene.ttt",  # idem
        "base_target":    (0.0, 0.0),
        "n_runs":         1000,
        "noise_std":      0.5,
        "wait_time":      10.0,
        "metrics": [
            "mse",
            "rmse",
            "mae",
            "mape",
            "dtw_cru",
            "dtw_norm",
            "frechet_xy",
            "edr_x",
            "edr_y",
            "pearson_x",
            "pearson_y",
            "lag_x_ms",
            "lag_y_ms"
        ],
        "startup_timeout": 20.0,  # mantido só por compatibilidade; não é usado aqui
    },
]

# -----------------------------------------------------------------------------
# Funções utilitárias
# -----------------------------------------------------------------------------
def _find_validator_py():
    """Tenta resolver o caminho do validator."""
    wd = Path(__file__).parent
    cand1 = wd / "validation" / "montecarlo_validator.py"
    cand2 = wd / "montecarlo_validator.py"
    if cand1.is_file():
        return cand1
    if cand2.is_file():
        return cand2
    raise FileNotFoundError("montecarlo_validator.py não encontrado em ./validation/ ou ./")

def launch_validator():
    """Inicia o processo do validator via Python."""
    wd = Path(__file__).parent
    val_path = _find_validator_py()
    return subprocess.Popen(
        [sys.executable, str(val_path)],
        cwd=str(wd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

def stop(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

def make_manifest(cfg, out_dir: Path):
    """Cria manifest.json com metadados da rodada."""
    manifest = {
        "scenario":  cfg["name"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed":      int(time.time()),
    }
    try:
        manifest["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        manifest["git_commit"] = None
    h = hashlib.sha256()
    for k, v in cfg.items():
        h.update(str(v).encode())
    manifest["config_hash"] = h.hexdigest()[:16]
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"Manifesto criado: {out_dir/'manifest.json'}")

# -----------------------------------------------------------------------------
# Função principal de cenário (sem lançamento do Coppelia)
# -----------------------------------------------------------------------------
def run_scenario(cfg):
    wd = Path(__file__).parent
    procs = {}

    # Diretório de saída desta rodada
    run_id = time.strftime("%Y%m%d_%H%M%S")
    out_dir = wd / "logs" / "experiments" / f"{cfg['name']}_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    make_manifest(cfg, out_dir)

    # 🔹 Salva o caminho do cenário atual para uso pelos scripts do Coppelia
    #    (as cenas já abertas podem ler este arquivo, então mantemos igual)
    current_run_file = wd / "logs" / "experiments" / "current_run.txt"
    current_run_file.write_text(str(out_dir), encoding="utf-8")
    print(f"[orchestrator] Current run path registrado em: {current_run_file}")

    # CSV de métricas
    csv_path = out_dir / "metrics.csv"
    with open(csv_path, "w", newline="") as f:
        csv.writer(f).writerow(["epoch"] + cfg["metrics"])

    try:
        print(f"\n=== {cfg['name']} (sem launch de Coppelia) ===")
        print(">> Certifique-se de que AGV, Twin e Fleet Manager já estão rodando e conectados ao broker.\n")

        # 1) Lança apenas o validator
        procs["val"] = launch_validator()

        # 2) Loop de Monte Carlo
        for epoch in range(1, cfg["n_runs"] + 1):
            # reset do validator
            procs["val"].stdin.write("reset\n")
            procs["val"].stdin.flush()
            _ = procs["val"].stdout.readline()  # lê a resposta do reset (se houver)

            # gera target aleatório em torno de base_target
            dx, dy = np.random.normal(0, cfg["noise_std"], size=2)
            xt = cfg["base_target"][0] + dx
            yt = cfg["base_target"][1] + dy

            # envia target pela função já existente
            send_target_position(xt, yt)
            print(f"> [Epoch {epoch}] x={xt:.3f}, y={yt:.3f}")

            # espera a simulação evoluir
            time.sleep(cfg["wait_time"])

            # solicita cálculo de métricas com retry
            line = ""
            for attempt in range(5):
                procs["val"].stdin.write("compute\n")
                procs["val"].stdin.flush()
                line = procs["val"].stdout.readline().strip()
                if line == "ERROR_NO_DATA":
                    print(f"[Epoch {epoch}] sem dados, retry {attempt+1}/5")
                    time.sleep(0.5)
                    continue
                break

            if line.startswith("ERROR"):
                raise RuntimeError(f"Validator retornou: {line}")

            vals = line.split(",")
            if len(vals) != len(cfg["metrics"]):
                raise RuntimeError(
                    f"{len(vals)} métricas retornadas, esperado {len(cfg['metrics'])}"
                )

            # grava no CSV
            with open(csv_path, "a", newline="") as f:
                csv.writer(f).writerow([epoch] + vals)
            print("   →", dict(zip(cfg["metrics"], vals)))

        print(f"[ok] Métricas registradas em: {csv_path}")

        # 3) Gera summary
        summary_path = out_dir / "summary.csv"
        df = pd.read_csv(csv_path)
        summary = df.drop(columns=["epoch"], errors="ignore").describe(
            percentiles=[0.05, 0.5, 0.95]
        )
        summary.to_csv(summary_path)
        print(f"[ok] Resumo salvo: {summary_path}")

    finally:
        # 4) cleanup -> apenas validator
        for name, p in procs.items():
            print(f"Encerrando {name}…")
            stop(p)

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, help="Sobrescreve n_runs para teste rápido")
    args = ap.parse_args()

    for scen in SCENARIOS:
        if args.runs:
            scen["n_runs"] = args.runs
        try:
            run_scenario(scen)
        except Exception as e:
            print(f"Erro em {scen['name']}: {e}")
            break
    else:
        print("\n=== Todos os cenários concluídos ===")

if __name__ == "__main__":
    main()
