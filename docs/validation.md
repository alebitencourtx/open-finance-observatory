> Relatório histórico da entrega 1.1.1. Para a versão atual, consulte [correcoes-1.2.0.md](correcoes-1.2.0.md) e o CI do repositório.

# Validação da entrega · 10/11/2026

O resultado principal está no [manual HTML único](documentacao.html) e no dashboard gerado em `dist/index.html`.

## Evidências locais

- CPython 3.12.10 no Windows; ambiente `.venv` isolado; dependências verificadas com `pip check`.
- **38 testes aprovados**, em 3,65 s na última execução da suíte. Cobrem integridade, contratos, paginação, retry, limites, unidades, escopo de produto, deduplicação, retomada e publicação.
- `node --check src/observatory/web/app.js` aprovado.
- Wheel Python construído com isolamento PEP 517; SQL, assets web e template HTML conferidos no pacote. JavaScript inline do manual também passou na verificação sintática.
- `observatory verify`: **169 objetos SHA-256 aprovados**.
- Comparação byte a byte por hash dos arquivos importados com a origem: **169 conferidos, zero divergências**.
- Gates estruturais aprovados; permanecem **7 endpoints incompletos**, **2 faixas de taxa invertidas** e **16 observações com unidade não comparável**. Essas condições são da publicação observada e ficam visíveis.
- Replay do Diretório salvo: **169 alvos e 15 empresas**, com evidências registradas no catálogo novo.
- Smoke real de rede em lake separado: endpoint público de empréstimos pessoais da Getnet, grupo Santander; HTTP 200, TLS verificado, 2 registros, 1 página. A publicação analítica continua baseada no instantâneo original.

## Execução real

| Item | Resultado |
|---|---:|
| Versão de transformação | 1.1.1 |
| Build | b382f6e22f3ddca667c73b4e |
| Snapshot | import-5085591ce24039e73119 |
| Bronze de entrada | 146.127.187 bytes |
| Endpoints | 169 |
| Tempo registrado do build sem cache de transformação | 12,433 s |
| Reutilização do build concluído e renderização | 0,101 s |
| Ofertas normalizadas distintas | 7.653 |
| Linhas de canais removidas por deduplicação | 8.231 |
| Registros em quarentena | 0 |

Os tempos pertencem a esta máquina e a esta execução; não são SLA ou comparação com a implementação anterior. O limite de 1 GB é configuração do DuckDB, não medição de RSS do processo.

## Navegador e documentação

Verificados via navegador local: visão executiva, matriz com detalhe de endpoints, busca de CDB, filtro de família, paginação, exportação real de 1.157 ofertas filtradas, pré/pós-fixados separados, seleção de conglomerados e ausência de erros de console nas telas verificadas.

Dashboard e documentação foram renderizados em áreas de 390 px de largura, sem overflow horizontal da página. Os menus móveis foram acionados por teclado. As tabelas e desenhos possuem rolagem interna quando necessário. O controle de viewport do ambiente não refletiu a dimensão solicitada; a verificação estreita foi feita com frames locais de largura explícita no mesmo navegador, removidos após a revisão.

A documentação tem 15 seções, três desenhos SVG ampliáveis, busca com acentos normalizados, schemas extraídos de Arrow e DuckDB, código copiável e impressão. A ampliação dos diagramas, a busca e a cópia foram acionadas e verificadas. Um teste estrutural garante ausência de assets externos de execução, IDs únicos, âncoras existentes e ausência de placeholders.

O navegador de validação aceita HTTP/HTTPS e bloqueou o protocolo `file:`. Assim, a inspeção visual ocorreu por HTTP local; a independência de arquivos externos foi verificada pelo conteúdo do HTML e pelo teste estrutural. Não houve tentativa de contornar essa política. O PDF não foi exportado ou homologado; o botão abre a impressão do navegador.

## Limites da homologação

CI remoto, Docker, outras versões de Python/SO, autenticação corporativa, cargas distribuídas e operação recorrente não foram executados nesta entrega. O coletor tem testes de falha e um smoke de rede, mas não foi feita nova coleta integral dos 169 endpoints. A documentação diferencia o instantâneo importado do smoke.

As prévias visuais estão em `docs/previews/`. Os relatórios detalhados de execução, smoke, auditoria de origem e desempenho estão em `artifacts/`, ignorados pelo Git.
