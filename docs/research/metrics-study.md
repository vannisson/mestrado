# Estudo e seleção de métricas

## Critérios de seleção

Uma métrica entra no núcleo quando possui interpretação ligada ao sinal, unidade ou
normalização explícita, comportamento conhecido em casos degenerados e teste com
resultado analítico. Nenhuma métrica isolada representa a credibilidade do twin.

## Métricas implementadas

| Grupo | Métricas | Contribuição | Principal limitação |
|---|---|---|---|
| Erro ponto a ponto | MSE, RMSE, MAE, NRMSE, máximo, P95 | Magnitude da divergência | Exige alinhamento temporal |
| Percentual | MAPE | Compatibilidade com o estudo original | Instável perto de zero; não é padrão |
| Temporal | DTW normalizado e restrito | Diferenças de forma com pequeno desalinhamento | Pode esconder atraso se usado sozinho |
| Temporal | Correlação cruzada/lag | Estimativa explícita do atraso | Indefinida para sinais constantes |
| Trajetória | ATE, RPE, endpoint, comprimento relativo | Acurácia global e drift local | Requer frames equivalentes |
| Orientação | Distância geodésica de quaternion | Erro angular fisicamente interpretável | Exige convenção de quaternion consistente |
| Controle | IAE, ISE, ITAE, erro estacionário | Qualidade acumulada de acompanhamento | Depende de referência temporal válida |
| Stream | frequência, jitter e duração | Qualidade do fluxo de dados | Não mede fidelidade física |
| Repetições | média, desvio, mediana e bootstrap 95% | Variabilidade e incerteza amostral | Requer múltiplos ensaios independentes |

## Candidatas ainda não promovidas

- Wasserstein para comparar distribuições entre repetições.
- Fréchet e Hausdorff para geometria de trajetórias.
- Chamfer e ICP-RMSE para nuvens de pontos ou varreduras LiDAR registradas.
- NEES/NIS quando o twin produzir covariância de estado.

Essas métricas só devem ser ativadas quando houver sinais, hipóteses e fixtures que
permitam verificar sua implementação. Para LiDAR, também será necessário separar
erro de pose do erro do próprio sensor antes de interpretar a distância entre scans.

