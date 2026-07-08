from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from dt_validation.core.models import CheckStatus
from dt_validation.core.replay import run_replay
from dt_validation.core.suite import run_suite
from dt_validation.metrics.registry import METRIC_REGISTRY

app = typer.Typer(
    no_args_is_help=True,
    help="Framework de verificação e validação de digital twins.",
)
console = Console()


@app.command()
def doctor() -> None:
    """Verifica se o núcleo e as integrações opcionais estão disponíveis."""
    table = Table("Componente", "Status", "Detalhe")
    table.add_row("Python", "PASS", sys.version.split()[0])
    lock = Path("uv.lock")
    table.add_row("uv.lock", "PASS" if lock.exists() else "WARN", str(lock.resolve()))
    coppelia = _find_coppelia()
    table.add_row(
        "CoppeliaSim 4.10.0",
        "NOT_CONFIGURED" if coppelia is None else "FOUND",
        "integração opcional nesta etapa" if coppelia is None else str(coppelia),
    )
    console.print(table)


@app.command()
def replay(config: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """Executa V&V offline a partir dos logs declarados no YAML."""
    outcome = run_replay(config)
    console.print(f"Resultado: [{_status_color(outcome.status)}]{outcome.status}[/]")
    console.print(f"Artefatos: {outcome.run_dir}")
    if outcome.status in {CheckStatus.FAIL, CheckStatus.INVALID}:
        raise typer.Exit(code=1)


@app.command()
def suite(path: Annotated[Path, typer.Argument(exists=True)]) -> None:
    """Executa uma matriz de configurações e compara com expected_status quando houver."""
    try:
        outcome = run_suite(path)
    except ValueError as error:
        console.print(str(error))
        raise typer.Exit(code=1) from error
    table = Table("Experimento", "Obtido", "Esperado", "Artefatos")
    for result in outcome.results:
        expected = result.expected
        expected_label = expected.value if expected is not None else "-"
        table.add_row(
            result.config.stem,
            f"[{_status_color(result.observed)}]{result.observed}[/]",
            expected_label,
            str(result.run_dir),
        )
    console.print(table)
    console.print(f"Resumo da suíte: {outcome.summary_json}")
    if outcome.status == CheckStatus.FAIL:
        raise typer.Exit(code=1)


@app.command("run")
def run_live(config: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """Reserva a interface da futura execução síncrona no CoppeliaSim."""
    del config
    console.print("A integração Coppelia/ZeroMQ ainda não está habilitada nesta etapa.")
    raise typer.Exit(code=2)


@app.command("metrics")
def list_metrics() -> None:
    """Lista os plugins quantitativos disponíveis."""
    table = Table("Métrica", "Unidade")
    for name, (_, unit) in sorted(METRIC_REGISTRY.items()):
        table.add_row(name, unit)
    console.print(table)


@app.command()
def report(run_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)]) -> None:
    """Localiza o relatório de uma execução já materializada."""
    report_path = run_dir / "report.html"
    if not report_path.exists():
        console.print(f"Relatório ausente: {report_path}")
        raise typer.Exit(code=1)
    console.print(report_path.resolve())


def _find_coppelia() -> Path | None:
    root = os.getenv("COPPELIASIM_ROOT")
    candidates = [] if root is None else [Path(root) / "coppeliaSim.exe"]
    executable = shutil.which("coppeliaSim") or shutil.which("coppeliaSim.exe")
    if executable:
        candidates.append(Path(executable))
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _status_color(status: CheckStatus) -> str:
    return "green" if status == CheckStatus.PASS else "red"


if __name__ == "__main__":
    app()
