# Metodologia de verificação e validação

## Objetivo

O framework separa duas perguntas que não devem ser usadas como sinônimos:

- **Verificação:** os requisitos foram implementados corretamente e a realização
  computacional corresponde ao modelo conceitual?
- **Validação:** a representação tem precisão suficiente para um contexto de uso
  explicitamente declarado?

Essa separação segue as definições e responde às lacunas descritas por Bitencourt,
Wooley e Harris em *Verification and validation of digital twins: a systematic
literature review for manufacturing applications* (2024), DOI
[`10.1080/00207543.2024.2357741`](https://doi.org/10.1080/00207543.2024.2357741).

## Fluxo obrigatório

1. Declarar contexto de uso, pergunta de interesse, envelope e limitações.
2. Registrar requisitos verificáveis ou validáveis, com identificador e criticidade.
3. Preservar configuração, versões, dados, seeds e parâmetros do experimento.
4. Verificar configuração, dados, integração, sincronização e reprodutibilidade.
5. Calcular evidências quantitativas adequadas a cada sinal.
6. Aplicar critérios de aceitação antes de emitir uma conclusão.
7. Gerar a matriz requisito → check → evidência → resultado.

## Gates e interpretação

Os estados possíveis são `PASS`, `FAIL`, `INVALID` e `SKIPPED`. Dados ausentes ou
uma métrica matematicamente inaplicável nunca são convertidos em zero. Um gate crítico
falho ou inválido impede a aprovação global.

A cobertura corresponde à fração de checks aplicáveis efetivamente executados. Ela
não é uma nota de confiança: evita condensar evidências heterogêneas em um número
arbitrário.

## Força da evidência

O manifesto distingue `simulation-to-simulation` de `physical-validation`. O primeiro
é apropriado para verificar a arquitetura, experimentar métricas e estudar
perturbações, mas não comprova fidelidade em relação ao mundo físico.

## Cobertura atual e evolução

O replay implementa requisitos, qualidade dos dados, alinhamento, métricas,
rastreabilidade e relatório. A etapa Coppelia acrescentará verificação de ciclo de
vida, entrega de comandos, timestep e stepping síncrono. Ensaios físicos deverão
acrescentar calibração, incerteza dos sensores e validade dentro do envelope real.

