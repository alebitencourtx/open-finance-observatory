# Operação local

O [manual HTML único](documentacao.html) contém o guia completo, desenhos e dicionário de dados.

1. Instalar as dependências dos locks em `.venv`, com `pip install --no-deps -e .` após os locks.
2. Escolher importação do bronze existente ou descoberta e coleta novas.
3. Verificar hashes com `observatory verify`.
4. Construir com `observatory build`; só um build aprovado avança `latest.json`.
5. Inspecionar `observatory status`, `quality.json` e o painel de qualidade.
6. Abrir `dist/index.html` ou usar `observatory serve` em loopback.
7. Gerar `observatory docs --output docs/documentacao.html` para a cópia independente do manual.

Os comandos usam o executável de `.venv` ou `python -m observatory.cli`. O parâmetro `--lake` é global e vem antes do subcomando. Evite rodar dois escritores no mesmo lake.

Em interrupção, use `collect --resume <id>`. Verifique o PID antes de remover um lock abandonado. Um snapshot fechado com falhas é revisado sob nova identidade; não é sobrescrito. Para rollback, use `build --snapshot <id-anterior>` e regenere a pasta de consumo.

Falhas HTTP e taxas inválidas são avisos de origem. Contrato malformado, ausência de endpoints ou referência órfã é bloqueante. Não elimine evidências para fazer um gate passar. Corrija a regra, incremente a versão de transformação e faça replay.

Não há exclusão automática de bronze nem agendamento configurado. Backups devem incluir objetos, snapshots e builds concluídos. O servidor local é um preview; distribuição corporativa exige infraestrutura própria de hosting/identidade.
