# Bancada sintética de V&V

Os cenários sintéticos servem como uma etapa intermediária entre o replay legado e a
execução ao vivo no CoppeliaSim. Eles não tentam substituir o experimento real: a função
é testar se o framework responde corretamente a perturbações conhecidas.

## Matriz inicial

| Configuração | Papel científico | Resultado esperado | Sinal de diagnóstico |
| --- | --- | --- | --- |
| `identity-pass.yaml` | Controle positivo sem perturbação | `PASS` | Métricas próximas de zero |
| `noise-pass.yaml` | Controle positivo com ruído leve | `PASS` | Erros abaixo de limiares preliminares |
| `delay-fail.yaml` | Controle negativo temporal | `FAIL` | Atraso por correlação cruzada |
| `drift-fail.yaml` | Controle negativo espacial | `FAIL` | ATE e erro final de posição |
| `dropout-fail.yaml` | Controle negativo de verificação | `FAIL` | Cobertura de alinhamento insuficiente |

Execute a matriz com:

```powershell
uv run dtv suite experiments/pioneer/synthetic
```

O comando usa o campo `expected_status` de cada YAML. Assim, uma falha esperada continua
sendo um sucesso da bancada, desde que o resultado observado bata com o diagnóstico
planejado.

Na calibração inicial sobre os logs legados do Pioneer, os controles produziram os
seguintes valores aproximados:

- identidade: ATE RMSE `0,000 m`;
- ruído leve: ATE RMSE `0,026 m`;
- atraso: atraso absoluto por correlação cruzada `0,501 s`;
- drift: ATE RMSE `0,346 m` e erro final `0,600 m`;
- dropout: falha de verificação por cobertura de alinhamento, mesmo com erro geométrico baixo.

## Relação com a dissertação

Essa etapa preserva a ideia central do projeto original: comparar sinais brutos da
referência e do candidato a twin. A diferença é que agora a comparação passa a ser
tratada como evidência de V&V. Cada perturbação sintética cria um pequeno ensaio
controlado para justificar por que uma métrica foi escolhida e que tipo de divergência
ela consegue revelar.
