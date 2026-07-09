# Plano complementar de trabalho

Este documento complementa o `PLAN.md` e registra o estado atual do framework de
verificação e validação de digital twins robóticos. A intenção é facilitar a retomada em
outra máquina e orientar os próximos marcos sem perder o vínculo com o projeto original
do mestrado.

## Estado atual

Branch de trabalho:

```text
feature/dt-validation-framework
```

Marcos já registrados em commits:

```text
08b5774 feat: add validation framework foundation
0e1c9d3 feat: add synthetic validation suite
7f77170 feat: add suite summaries
```

O projeto deixou de ser apenas um conjunto de scripts acoplados às duas simulações
originais e passou a ter uma primeira estrutura de framework. O código legado foi
preservado em `legacy/`, enquanto o novo núcleo está em `src/dt_validation/`.

## O que já foi implementado

### Fundação do framework

Foi criada uma estrutura Python empacotada com `uv`, `pyproject.toml`,
`.python-version` e `uv.lock`. A CLI principal é exposta pelo comando `dtv`.

Componentes principais:

- `core/`: modelos, carregamento de configuração, alinhamento temporal, replay e suíte;
- `adapters/`: contratos e fontes de dados;
- `metrics/`: métricas quantitativas;
- `vv/`: avaliação de requisitos, gates e evidências;
- `reporting/`: artefatos, gráficos e relatório HTML;
- `experiments/`: configurações YAML dos experimentos;
- `docs/research/`: documentação metodológica.

O framework agora trabalha com participantes explícitos:

- `reference`: fonte de referência, simulada ou física;
- `candidate`: candidato a digital twin.

Isso permite distinguir uma comparação simulação-simulação de uma validação contra uma
referência física. Essa distinção é importante para a defesa metodológica do trabalho.

### Replay offline dos logs legados

Foi implementado o adapter `csv`, capaz de ler os logs existentes em:

```text
logs/agv_logs
logs/twin_logs
```

O experimento principal atual é:

```text
experiments/pioneer/replay.yaml
```

Ele compara os logs do Pioneer legado, alinha os sinais por tempo decorrido e calcula
métricas de posição, orientação, velocidades e sinais de IMU. Esse replay é um controle
negativo importante: o candidato legado possui atraso artificial, então o resultado
global esperado é `FAIL`.

### Métricas e requisitos

Foram implementadas métricas de:

- erro ponto a ponto: `mse`, `rmse`, `mae`, `mape`, `nrmse`;
- erro robusto: máximo, percentil 95 e erro estacionário;
- trajetória: `ate_rmse`, `endpoint_error`, `rpe_translation_rmse`,
  `path_length_relative_error`;
- orientação: distância geodésica entre quaternions;
- temporalidade: `normalized_dtw`, `cross_correlation_lag`,
  `absolute_cross_correlation_lag`;
- controle: `iae`, `ise`, `itae`.

As métricas não são mais apenas impressas ou salvas isoladamente. Elas alimentam
requisitos declarados no YAML. Cada requisito define:

- tipo: verificação ou validação;
- sinal avaliado;
- métrica usada;
- operador;
- limiar;
- criticidade;
- justificativa.

### Geração de evidências

Cada execução de replay gera um dossiê em:

```text
artifacts/<experimento>/<run-id>/
```

Conteúdo típico:

- `manifest.json`;
- `observations.parquet`;
- `metrics.json`;
- `metrics.csv`;
- `evidence.json`;
- `traceability.csv`;
- `report.html`;
- gráficos em `plots/`.

Esses artefatos não são versionados no Git, mas são essenciais para auditoria local e
para a escrita da dissertação.

### Bancada sintética de validação

Foi criado o adapter `synthetic`, que deriva candidatos artificiais a partir dos logs da
referência. Ele permite injetar perturbações conhecidas sem depender ainda do CoppeliaSim.

Cenários disponíveis:

```text
experiments/pioneer/synthetic/identity-pass.yaml
experiments/pioneer/synthetic/noise-pass.yaml
experiments/pioneer/synthetic/delay-fail.yaml
experiments/pioneer/synthetic/drift-fail.yaml
experiments/pioneer/synthetic/dropout-fail.yaml
```

Papel de cada cenário:

| Cenário | Perturbação | Resultado esperado |
| --- | --- | --- |
| `identity-pass` | nenhuma | `PASS` |
| `noise-pass` | ruído leve | `PASS` |
| `delay-fail` | atraso de 500 ms | `FAIL` |
| `drift-fail` | drift espacial de 60 cm | `FAIL` |
| `dropout-fail` | perda de amostras | `FAIL` |

A suíte sintética é executada com:

```powershell
uv run dtv suite experiments/pioneer/synthetic
```

Ela compara o resultado observado com o campo `expected_status` de cada YAML. A execução
gera resumos persistentes em:

```text
artifacts/suites/synthetic/<run-id>/suite.json
artifacts/suites/synthetic/<run-id>/suite.csv
```

Na calibração atual, a suíte passa: os cenários positivos passam e os negativos falham
pelas razões esperadas.

## Como retomar em outra máquina

Pré-requisitos:

- Git;
- Python compatível com o `.python-version`;
- `uv` instalado;
- acesso ao repositório no GitHub.

Fluxo recomendado:

```powershell
git clone https://github.com/vannisson/mestrado.git
cd mestrado
git switch feature/dt-validation-framework
uv sync --locked
uv run dtv doctor
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen pytest
uv run --frozen dtv suite experiments/pioneer/synthetic
```

Observação: o comando abaixo é esperado retornar `FAIL`, porque o experimento legado
possui uma divergência proposital/relevante no candidato:

```powershell
uv run --frozen dtv replay experiments/pioneer/replay.yaml
```

Isso não indica erro de software. Ele funciona como controle negativo e deve gerar um
dossiê de evidência em `artifacts/`.

## Limitações atuais

- O comando `dtv run` ainda é placeholder.
- A integração ao vivo com CoppeliaSim/ZeroMQ ainda não foi implementada.
- Os limiares de validação ainda são preliminares.
- A evidência atual é majoritariamente simulação-simulação, não validação física.
- TurtleBot3 ainda não foi modelado como caso funcional.
- O adapter de robô físico ainda não existe.

## Próximos passos recomendados

### 1. Implementar o adapter CoppeliaSim de forma mockável

Este deve ser o próximo marco técnico. A implementação deve preservar o contrato de
`ParticipantAdapter`, permitindo que `csv`, `synthetic`, CoppeliaSim e futuramente robô
real sejam trocados por configuração.

Primeiro objetivo:

- criar `CoppeliaSimAdapter`;
- criar uma camada pequena de cliente ZeroMQ;
- permitir testes com cliente falso, sem abrir o CoppeliaSim;
- validar ciclo `prepare`, `start`, `step`, `observations` e `stop`.

Critério de aceitação inicial:

```text
pytest passa com um adapter CoppeliaSim mockado e dtv doctor reconhece a configuração opcional.
```

### 2. Declarar cenas e mapeamentos por YAML

O framework precisa permitir que uma nova cena seja adicionada sem alterar o núcleo.
O YAML deve declarar:

- caminho da cena;
- porta ZeroMQ;
- timestep;
- objetos de pose;
- juntas das rodas;
- sensores;
- frames;
- unidades;
- aliases de sinais.

Isso prepara a transição do Pioneer atual para TurtleBot3.

### 3. Implementar execução sincronizada

Depois do adapter mockado, a execução real deve usar stepping sincronizado:

1. aplicar o mesmo comando à referência e ao candidato;
2. avançar ambos um passo;
3. coletar observações no mesmo tempo lógico;
4. persistir os dados;
5. calcular métricas ao final.

O objetivo é evitar que a comparação dependa da ordem de chegada de mensagens.

### 4. Evoluir a bancada sintética

A bancada sintética atual já funciona como controle de sanidade. Ela pode ser ampliada
para estudo de sensibilidade:

- varrer vários atrasos: 50 ms, 100 ms, 250 ms, 500 ms;
- varrer ruídos de posição/orientação;
- varrer drift;
- testar perda aleatória de amostras;
- produzir curvas de limiar para justificar requisitos.

Esse bloco tem alto valor para a dissertação, porque ajuda a justificar por que cada
métrica foi escolhida.

### 5. Calibrar limiares de validação

Os thresholds atuais são experimentais. O próximo passo científico é justificar:

- qual erro de posição é aceitável;
- qual erro angular é aceitável;
- qual atraso temporal torna o twin inadequado;
- quais métricas são mais informativas por tipo de divergência;
- quais conclusões são válidas apenas dentro do envelope operacional.

### 6. Preparar TurtleBot3 como segundo caso

Depois do Pioneer estar estável no fluxo CoppeliaSim, o TurtleBot3 deve entrar como
novo caso de uso. Idealmente, isso deve exigir apenas:

- nova cena;
- novo YAML de mapeamento;
- novos requisitos;
- talvez novos sinais.

O núcleo do framework não deve precisar ser alterado.

### 7. Planejar o adapter físico

O robô real deve entrar futuramente como outro `ParticipantAdapter`. A pipeline de
validação deve continuar a mesma:

```text
reference físico -> observations -> alignment -> metrics -> requirements -> evidence
```

Essa etapa muda a classe da evidência de `simulation-to-simulation` para validação com
referência física.

## Próximo marco sugerido

Commit sugerido para o próximo bloco:

```text
feat: add coppelia adapter skeleton
```

Escopo esperado:

- contrato de configuração do CoppeliaSim;
- adapter com cliente injetável;
- fake client para testes;
- testes unitários do ciclo de vida;
- `dtv doctor` verificando variáveis/caminhos opcionais;
- documentação curta em `docs/research/coppelia-integration.md`.

Esse marco ainda não precisa abrir o simulador. A prioridade é deixar a arquitetura
correta e testável antes de conectar no CoppeliaSim real.
