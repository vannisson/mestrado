# Framework de V&V para Digital Twins no CoppeliaSim

## Resumo

Evoluir o projeto no branch `feature/dt-validation-framework`, preservando o experimento Pioneer como primeiro caso de uso. A v1 executará replay dos logs e duas cenas CoppeliaSim 4.10.0 em lockstep via ZeroMQ, com CLI/YAML, dependências gerenciadas por `uv` e dossiê de evidências por execução.

O framework seguirá as lacunas identificadas por [Bitencourt, Wooley e Harris](https://www.tandfonline.com/doi/full/10.1080/00207543.2024.2357741): objetivos distintos de verificação e validação, rastreabilidade de requisitos, metodologia padronizada, métricas objetivas e cobertura de evidências.

## Estrutura e interfaces

```text
src/dt_validation/
├── adapters/       # contratos e integração Coppelia
├── core/           # observações, comandos, runner e alinhamento
├── metrics/        # plugins de métricas
├── vv/             # requisitos, gates e rastreabilidade
├── reporting/      # artefatos, gráficos e relatório
└── cli.py

experiments/        # YAMLs, cenários, requisitos e mapeamentos das cenas
scenes/pioneer/     # cenas-fonte e candidato
tests/              # unitários, replay, integração e golden data
docs/research/      # metodologia de V&V e estudo de métricas
legacy/             # implementação atual arquivada
artifacts/          # execuções geradas, ignoradas pelo Git
```

- Criar `pyproject.toml`, `.python-version` fixada em Python 3.11 e `uv.lock`; o lock será a fonte exata das versões, validada com `uv lock --check` e `uv sync --locked`, conforme o fluxo oficial do [uv](https://docs.astral.sh/uv/concepts/projects/sync/).
- Substituir `requirements.txt` por dependências runtime e grupo `dev`: NumPy, SciPy, pandas, PyArrow, Pydantic, PyYAML, Typer, Jinja2, Matplotlib, cliente ZeroMQ do Coppelia 2.0.4, pytest, pytest-asyncio, pytest-cov, Ruff e mypy.
- Expor os comandos `dtv doctor`, `dtv run`, `dtv replay`, `dtv report` e `dtv metrics`.
- Definir tipos públicos: `Observation`, `Command`, `Scenario`, `ParticipantSpec`, `SignalSpec`, `Requirement`, `MetricResult`, `CheckResult`, `Evidence` e `RunManifest`.
- Definir `ParticipantAdapter` com ciclo `prepare → start → apply_command → observe → step → stop` e capacidades declaradas, sem dependência de Coppelia, MQTT ou ROS 2.
- Usar papéis `reference` e `candidate`, registrando `reference_kind: simulated|physical`. Resultados com referência simulada serão identificados explicitamente como evidência simulation-to-simulation.

## CoppeliaSim e fluxo experimental

- Fixar CoppeliaSim Edu 4.10.0 como baseline; `dtv doctor` localizará o executável por configuração ou `COPPELIASIM_ROOT`, verificará versão, plugin ZeroMQ, cenas, portas e objetos necessários.
- Executar duas instâncias headless nas portas `23000/23001` e `23002/23003`, usando `-GzmqRemoteApi.rpcPort`. O modo stepping oficial permite sincronização por tempo de simulação, em vez de chegada de mensagens ([documentação](https://manual.coppeliarobotics.com/en/simulation.htm)).
- Deixar as cenas finas: geometria, dinâmica, juntas e sensores. Orquestração, logging, controle e métricas ficam no pacote Python externo.
- Declarar em YAML os caminhos dos objetos, rodas, sensores, frames, unidades, timestep e motor físico. Uma nova cena será integrada criando outro mapeamento, sem alterar o núcleo.
- Extrair o controlador diferencial atual para um plugin externo. Ele lerá a pose da referência, calculará as velocidades-alvo e aplicará o mesmo comando às duas cenas antes de cada passo; o candidato evoluirá sem injeção de pose.
- Suportar inicialmente comandos `TargetPosition`, `Twist` e `WheelVelocity`.
- A cada passo: aplicar comando, avançar ambas as cenas, capturar observações no mesmo tempo lógico, validar qualidade e persistir os dados.
- Encerrar processos com timeout e limpeza garantida, mesmo em falha parcial.

## Processo de V&V e métricas

Cada experimento declarará contexto de uso, pergunta de interesse, envelope operacional, requisitos quantificáveis, criticidade, método de evidência e critério de aceitação.

Verificação:

- completude e consistência dos requisitos;
- validade do modelo conceitual, hipóteses, frames, unidades e mapeamento da cena;
- testes de código e métricas contra resultados conhecidos;
- conexão, ciclo de vida e integração dos adaptadores;
- integridade, sequência e monotonicidade dos dados;
- sincronização entre participantes e repetibilidade por seed;
- entrega idêntica de comandos e funcionamento do cenário;
- registro de versões, parâmetros físicos, hashes e configuração.

Validação:

- adequação da referência e qualidade dos dados;
- comparação operacional dentro do contexto de uso;
- atendimento dos limiares por cenário e sinal;
- repetibilidade estatística e intervalo de confiança;
- robustez a atraso, ruído e variações de parâmetros;
- análise de sensibilidade e incerteza;
- conclusão limitada ao envelope testado e ao tipo de referência.

Cada gate produzirá `PASS`, `FAIL`, `INVALID` ou `SKIPPED`. Gates críticos determinarão o resultado global; o relatório mostrará cobertura das evidências aplicáveis, sem criar uma nota arbitrária de confiança.

Métricas implementadas na v1:

- Compatibilidade: MSE, RMSE, MAE e MAPE com proteção para valores próximos de zero; MAPE não será padrão.
- Erro de sinal: NRMSE, máximo, percentil 95 e erro estacionário.
- Temporal: DTW normalizado com janela restrita, correlação cruzada e lag estimado.
- Trajetória: erro euclidiano, ATE, RPE translacional/rotacional, erro final e erro relativo de comprimento.
- Orientação: distância geodésica entre quaternions.
- Controle: IAE, ISE, ITAE, overshoot e tempo de acomodação quando aplicáveis.
- Comunicação: latência, jitter, frequência efetiva, perda e desordenação.
- Repetições: média, desvio, mediana e intervalo bootstrap de 95%.

O estudo de métricas documentará fórmula, unidade, pressupostos, invariâncias, limitações e aplicabilidade. Wasserstein, Fréchet/Hausdorff, Chamfer e ICP-RMSE serão avaliadas para distribuições, trajetórias e LiDAR, mas só promovidas a plugins após haver sinais e casos de teste adequados.

## Execuções, evidências e testes

Cada execução criará:

```text
artifacts/<experimento>/<run-id>/
├── manifest.json
├── observations.parquet
├── metrics.json
├── metrics.csv
├── evidence.json
├── traceability.csv
├── report.html
└── logs/
```

O manifesto registrará Git SHA, configuração e hashes das cenas, versão do lock, CoppeliaSim, motor físico, timestep, seed, SO e motivo de qualquer invalidação.

Sequência de implementação:

1. Criar o branch, ignorar o PDF local e arquivar imediatamente código antigo em `legacy/`.
2. Inicializar o pacote `uv`, CLI, modelos, schemas YAML e adaptador em memória.
3. Implementar replay dos CSVs, alinhamento temporal, métricas e golden tests.
4. Implementar requisitos, rastreabilidade, gates e relatório de evidências.
5. Migrar Pioneer e controlador para o adaptador ZeroMQ externo.
6. Executar as duas cenas em stepping sincronizado e alcançar paridade funcional.
7. Adicionar cenários de atraso, ruído e variação física, demonstrando gates que passam e falham.
8. Consolidar metodologia e estudo acadêmico das métricas.

Critérios de aceitação:

- `uv sync --locked`, lint, tipos e testes passam em ambiente limpo.
- Replay existente gera artefatos determinísticos e nenhuma métrica silenciosamente inválida.
- Duas cenas executam ao menos 1.000 passos sincronizados e encerram sem processos órfãos.
- Cenário nominal passa os requisitos configurados.
- Perturbações controladas fazem falhar as evidências correspondentes.
- Uma cena com aliases diferentes pode ser adicionada apenas por YAML.
- O relatório distingue corretamente verificação, validação e limitações de uma referência simulada.

## Premissas

- O PDF permanecerá local e será incluído no `.gitignore`.
- Não haverá site de documentação; a metodologia ficará em Markdown no repositório.
- Pioneer será o único robô funcional da v1; TurtleBot3 e robô físico usarão futuramente o mesmo contrato de adaptador.
- ROS 2 e MQTT não entram no runtime principal da v1.
- A entrega completa ao vivo depende da instalação local do CoppeliaSim Edu 4.10.0; sem ela, somente núcleo e replay poderão ser aceitos.
