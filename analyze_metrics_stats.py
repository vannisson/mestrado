#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
analyze_metrics_stats.py
==========================================
Análise estatística dos resultados das métricas
para os três cenários (nominal / atraso / modelo
perturbado) do experimento de dual simulation.

- Lê CSVs em:
    final_results/normal/metrics.csv
    final_results/delay/metrics.csv
    final_results/wrong_model/metrics.csv

- Gera:
    summary_descriptive_stats.csv     -> resumo descritivo + IC95%
    summary_descriptive_stats.tex     -> tabela LaTeX (opcional, simples)
    summary_tests_kruskal_mw.csv      -> testes Kruskal + Mann-Whitney
    summary_effect_sizes.csv          -> tamanhos de efeito (Cohen's d, Cliff's delta)

Requisitos:
    pip install numpy pandas scipy
"""

from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats


# ============================================================
# Configuração
# ============================================================

# Pasta base onde estão os resultados
BASE_DIR = Path("final_results")

# Mapeamento: nome da pasta -> rótulo legível
SCENARIOS = {
    "normal": "Nominal",
    "delay": "Atraso",
    "wrong_model": "Modelo_perturbado",
}

# Se quiser fixar as métricas manualmente, preencha aqui.
# Caso deixe como None, o script descobre automaticamente
# todas as colunas numéricas (exceto 'scenario').
METRICS = None  # Ex: ["rmse_xy", "dtw_norm", "lag_avg"]


# ============================================================
# Funções auxiliares
# ============================================================

def load_all_data(base_dir: Path, scenarios_map: dict) -> pd.DataFrame:
    """
    Lê todos os metrics.csv e concatena em um único DataFrame
    adicionando a coluna 'scenario' com o rótulo legível.
    """
    dfs = []
    for folder, label in scenarios_map.items():
        csv_path = base_dir / folder / "metrics.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {csv_path}")
        df = pd.read_csv(csv_path)
        df["scenario"] = label
        dfs.append(df)

    data = pd.concat(dfs, ignore_index=True)
    return data


def mean_ci(x: pd.Series, alpha: float = 0.05):
    """
    Retorna média e IC (1 - alpha) para a média assumindo
    aproximação normal (n grande).
    """
    x = np.asarray(x.dropna())
    n = len(x)
    if n == 0:
        return np.nan, np.nan, np.nan

    m = x.mean()
    se = x.std(ddof=1) / np.sqrt(n)
    # z para 95% ~ 1.96; poderia generalizar com norm.ppf, mas assim é suficiente
    z = 1.96 if np.isclose(alpha, 0.05) else stats.norm.ppf(1 - alpha / 2.0)
    ci_low = m - z * se
    ci_high = m + z * se
    return m, ci_low, ci_high


def summarize_descriptive_stats(
    data: pd.DataFrame,
    metrics: list,
    scenario_col: str = "scenario",
) -> pd.DataFrame:
    """
    Gera DataFrame com estatísticas descritivas e IC95% por métrica × cenário.
    """
    rows = []

    scenarios = data[scenario_col].unique()
    for metric in metrics:
        for scenario in scenarios:
            x = data.loc[data[scenario_col] == scenario, metric]

            mean, ci_low, ci_high = mean_ci(x)
            std = x.std(ddof=1)
            median = x.median()
            q1 = x.quantile(0.25)
            q3 = x.quantile(0.75)
            n = x.notna().sum()

            row = {
                "metric": metric,
                "scenario": scenario,
                "n": int(n),
                "mean": mean,
                "std": std,
                "median": median,
                "iqr_low": q1,
                "iqr_high": q3,
                "ci_low": ci_low,
                "ci_high": ci_high,
            }
            rows.append(row)

    summary = pd.DataFrame(rows)
    return summary


def kruskal_and_mannwhitney(
    data: pd.DataFrame,
    metrics: list,
    scenario_col: str = "scenario",
) -> pd.DataFrame:
    """
    Roda Kruskal–Wallis global e, se significativo,
    faz Mann–Whitney pareado entre cenários.
    Retorna um DataFrame com resultados dos testes.
    """
    scenarios = data[scenario_col].unique()
    results = []

    for metric in metrics:
        # Global Kruskal–Wallis
        groups = [data.loc[data[scenario_col] == s, metric].dropna() for s in scenarios]
        H, p_global = stats.kruskal(*groups)

        # Armazena resultado global
        results.append(
            {
                "metric": metric,
                "test_type": "Kruskal-Wallis",
                "scenario_a": "ALL",
                "scenario_b": "ALL",
                "statistic": H,
                "p_value": p_global,
            }
        )

        # Pós-hoc Mann–Whitney (par a par)
        for a, b in combinations(scenarios, 2):
            x = data.loc[data[scenario_col] == a, metric].dropna()
            y = data.loc[data[scenario_col] == b, metric].dropna()

            if len(x) == 0 or len(y) == 0:
                continue

            U, p = stats.mannwhitneyu(x, y, alternative="two-sided")
            results.append(
                {
                    "metric": metric,
                    "test_type": "Mann-Whitney",
                    "scenario_a": a,
                    "scenario_b": b,
                    "statistic": U,
                    "p_value": p,
                }
            )

    tests_df = pd.DataFrame(results)
    return tests_df


def cohens_d(x: np.ndarray, y: np.ndarray) -> float:
    """
    Cohen's d para dois grupos independentes.
    """
    x = np.asarray(x)
    y = np.asarray(y)
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return np.nan

    vx = x.var(ddof=1)
    vy = y.var(ddof=1)

    # pooled std
    s_pooled = np.sqrt(((nx - 1) * vx + (ny - 1) * vy) / (nx + ny - 2))
    if s_pooled == 0:
        return np.nan

    return (x.mean() - y.mean()) / s_pooled


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """
    Cliff's delta (versão O(n*m), suficiente para n~1000).
    Delta > 0 -> x tende a ser maior que y.
    """
    x = np.asarray(x)
    y = np.asarray(y)
    n, m = len(x), len(y)
    if n == 0 or m == 0:
        return np.nan

    greater = 0
    lower = 0
    for xi in x:
        greater += np.sum(xi > y)
        lower += np.sum(xi < y)
    delta = (greater - lower) / (n * m)
    return float(delta)


def compute_effect_sizes(
    data: pd.DataFrame,
    metrics: list,
    scenario_col: str = "scenario",
) -> pd.DataFrame:
    """
    Calcula tamanhos de efeito (Cohen's d e Cliff's delta)
    para cada par de cenários e métrica.
    """
    scenarios = data[scenario_col].unique()
    rows = []

    for metric in metrics:
        for a, b in combinations(scenarios, 2):
            x = data.loc[data[scenario_col] == a, metric].dropna().values
            y = data.loc[data[scenario_col] == b, metric].dropna().values

            if len(x) < 2 or len(y) < 2:
                continue

            d = cohens_d(x, y)
            delta = cliffs_delta(x, y)

            rows.append(
                {
                    "metric": metric,
                    "scenario_a": a,
                    "scenario_b": b,
                    "cohens_d": d,
                    "cliffs_delta": delta,
                }
            )

    effects_df = pd.DataFrame(rows)
    return effects_df


def to_latex_table_descriptive(summary: pd.DataFrame, out_path: Path):
    """
    Gera uma tabela LaTeX simples com estatísticas descritivas.
    Você pode ajustar o formato depois no LaTeX da dissertação.
    """
    # Ordenar por métrica e cenário para ficar mais organizado
    df = summary.copy()
    df = df.sort_values(by=["metric", "scenario"])

    # Formatar algumas colunas (opcional)
    df["mean_std"] = df["mean"].map("{:.4f}".format) + " ± " + df["std"].map("{:.4f}".format)
    df["median_iqr"] = (
        df["median"].map("{:.4f}".format)
        + " ["
        + df["iqr_low"].map("{:.4f}".format)
        + "; "
        + df["iqr_high"].map("{:.4f}".format)
        + "]"
    )
    df["ci"] = (
        "["
        + df["ci_low"].map("{:.4f}".format)
        + "; "
        + df["ci_high"].map("{:.4f}".format)
        + "]"
    )

    table = df[["metric", "scenario", "n", "mean_std", "median_iqr", "ci"]]

    latex_str = table.to_latex(
        index=False,
        escape=False,
        column_format="llclll",
        header=[
            "Métrica",
            "Cenário",
            "n",
            "Média ± DP",
            "Mediana [IQR]",
            "IC95\\% da média",
        ],
    )

    out_path.write_text(latex_str, encoding="utf-8")


# ============================================================
# Main
# ============================================================

def main():
    print("Carregando dados...")
    data = load_all_data(BASE_DIR, SCENARIOS)

    # Descobrir métricas automaticamente, se não definidas
    global METRICS
    if METRICS is None:
        # Todas as colunas numéricas, exceto 'scenario'
        numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
        METRICS = numeric_cols
        print("Métricas detectadas automaticamente:", METRICS)
    else:
        print("Métricas definidas manualmente:", METRICS)

    # --------------------------------------------------------
    # Estatísticas descritivas + IC95%
    # --------------------------------------------------------
    print("\nGerando estatísticas descritivas...")
    summary = summarize_descriptive_stats(data, METRICS, scenario_col="scenario")
    summary_path = Path("summary_descriptive_stats.csv")
    summary.to_csv(summary_path, index=False)
    print(f"Salvo: {summary_path.resolve()}")

    latex_path = Path("summary_descriptive_stats.tex")
    to_latex_table_descriptive(summary, latex_path)
    print(f"Salvo (LaTeX): {latex_path.resolve()}")

    # --------------------------------------------------------
    # Testes estatísticos: Kruskal + Mann–Whitney
    # --------------------------------------------------------
    print("\nRodando testes de hipótese (Kruskal + Mann–Whitney)...")
    tests_df = kruskal_and_mannwhitney(data, METRICS, scenario_col="scenario")
    tests_path = Path("summary_tests_kruskal_mw.csv")
    tests_df.to_csv(tests_path, index=False)
    print(f"Salvo: {tests_path.resolve()}")

    # --------------------------------------------------------
    # Tamanhos de efeito: Cohen's d + Cliff's delta
    # --------------------------------------------------------
    print("\nCalculando tamanhos de efeito (Cohen's d, Cliff's delta)...")
    effects_df = compute_effect_sizes(data, METRICS, scenario_col="scenario")
    effects_path = Path("summary_effect_sizes.csv")
    effects_df.to_csv(effects_path, index=False)
    print(f"Salvo: {effects_path.resolve()}")

    print("\nConcluído!")


if __name__ == "__main__":
    main()
