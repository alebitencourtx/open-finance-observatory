# Documentação do Observatory OpenData

A referência completa é o **[manual HTML único publicado](https://alebitencourtx.github.io/open-finance-observatory/documentacao.html)**. A [cópia do repositório](documentacao.html) funciona offline, com estilos, scripts, schemas e diagramas embutidos. A cópia do Pages é gerada com a extração aprovada de cada deploy; a cópia no Git registra o estado usado na última geração documental.

| Artefato | Uso |
|---|---|
| `documentacao.html` | Funcional, regras, uso das oito seções, arquitetura/fluxo/ER, dicionário Arrow/SQL, código, operação, TLS, gates e recuperação |
| [Atualização remota](atualizacao-remota.md) | Procedimento breve do Actions, atual/anterior e diagnóstico de publicação |
| [Correções 1.2.0](correcoes-1.2.0.md) | Registro histórico das mudanças de normalização; não substitui o manual atual |
| [Plano](../PLAN.md) | Análise e decisões anteriores à implantação; preservar como histórico |
| `previews/` | Referências visuais históricas; não determinam o contrato da publicação atual |

Os comandos devem ser executados em `teste-opendata/observatory-opendata/`, com ambiente deste projeto. Para uma reprodução demonstrativa, use o ZIP de `datasets/`. Para reproduzir a produção, restaure um pacote `extraction-` aprovado em Releases, verifique hashes e reconstrua em lake separado. Os comandos completos estão no HTML.

## Atualizar o manual

1. Conferir a documentação contra `collect.py`, `normalize.py`, `sql/marts.sql`, `snapshots.py`, `tls.py`, CLI e workflows.
2. Editar os templates `src/observatory/templates/manual.html` e `operations.html`; editar o gerador `documentation.py` para evidências, schemas e código incorporados. Não editar somente o HTML gerado.
3. Usar um lake com a extração aprovada e gerar o build; em seguida executar `observatory.cli docs` com o mesmo lake e destino `docs/documentacao.html`.
4. Verificar testes, âncoras, busca, diagramas ampliáveis, layout móvel, impressão e ausência de dependências externas de renderização.
5. Commit/push republica a extração aprovada. Conferir Actions, URLs e identidade do snapshot; uma mudança documental não exige nova coleta.

```powershell
# Adapte o caminho ao lake restaurado que está sendo documentado.
.\.venv\Scripts\python.exe -m observatory.cli --lake .runtime/verified-current build --output dist
.\.venv\Scripts\python.exe -m observatory.cli --lake .runtime/verified-current docs --output docs/documentacao.html
.\.venv\Scripts\python.exe -m pytest -q tests/test_documentation.py
```

Os hashes de arquivos operacionais incorporados no manual identificam o conteúdo do checkout. O SHA Git é informado pelo ambiente do Actions quando disponível. A versão do pacote, a transformação, o snapshot, o build e a revisão documental são identificadores diferentes.

O [Admin Metrics Santander](https://alebitencourtx.github.io/admin-metrics/documentacao.html) tem documentação, estado, repo e agenda próprios. Seu cron de duas horas não atualiza este OpenData.
