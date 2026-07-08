# DT Validation

Framework experimental de verificação e validação (V&V) de digital twins robóticos.
O primeiro caso de uso preserva o Pioneer 3-DX da dissertação e compara os logs da
simulação de referência com os do candidato a twin.

## Início rápido

```powershell
uv sync --locked
uv run dtv doctor
uv run dtv replay experiments/pioneer/replay.yaml
```

Cada replay produz um dossiê em `artifacts/<experimento>/<run-id>/`, contendo dados,
métricas, evidências, matriz de rastreabilidade e relatório HTML. Uma referência
simulada é sempre identificada como evidência *simulation-to-simulation*; o framework
não a apresenta como validação física.

O código anterior está preservado em `legacy/`. A integração ao vivo com o
CoppeliaSim será implementada sobre os mesmos contratos usados pelo replay.

