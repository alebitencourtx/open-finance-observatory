# Correções e validação — transformação 1.2.0

Implementação autorizada após a revisão em `PLAN.md`, em 10/11/2026.

| Achado | Implementação |
|---|---|
| B01 | Lock no destino; geração em staging; releases imutáveis; commit por substituição atômica da entrada. Cada dashboard usa o manual de sua própria release |
| B02 | Finalização idempotente de snapshot aberto sem endpoints pendentes |
| B03 | Rejeição de objetos vazios, coleções de tipo incorreto e elementos aninhados inválidos; quarentena contabilizada. São contratos analíticos mínimos, sem promessa de validação OpenAPI integral |
| B04 | Validação de metadados, totais inteiros não negativos, divergência em ambas as direções e página vazia prematura; falha isolada por captura |
| B05 | Identidades de taxa/tarifa usam caminho relativo à oferta; repetição da oferta em outra posição não duplica entidades-filhas |
| B06 | Tarifas recebem validade e motivo; faixas inválidas são preservadas e excluídas dos marts; gate de aviso específico |
| B07 | Família unarranged identificada como adiantamento a depositantes; cheque especial permanece modalidade de empréstimos |
| B08 | VET conserva mínimo, máximo, faixas e contexto; nova visão de câmbio/VET e exportação |
| B09 | Faixa efetiva invertida de pós-fixados deixa de ser aceita silenciosamente |
| B10 | Chave silver usa conteúdo e identidade estável; metadados de captura são rematerializados em hits de cache |
| B11 | Bronze verificado antes de todo build; checksums silver/gold conferidos antes do reuso; hash do código/SQL participa da identidade do build |
| B12 | Exportação de taxas inclui tarifas, com discriminador de conjunto e união de colunas; tarifas podem ser exportadas mesmo sem taxas |
| B13 | Data e origem dinâmicas no manual; homologação histórica separada da evidência do build |

Também foram acrescentados recortes de taxa por modalidade, tarifas por código/serviço/moeda, preservação de foco após filtros, estado acessível de ordenação e disponibilidade do relatório em larguras intermediárias.

## Evidências locais

- **55 testes aprovados** no Windows/Python 3.12, incluindo 17 cenários adicionais de regressão.
- JavaScript aprovado por `node --check`.
- Reprocessamento dos 169 envelopes reais, 146.127.187 bytes, sem quarentena.
- Ofertas distintas: **7.653**; deduplicações: **49 tarifas**, **8 taxas**, **66 produtos** e **8.231 canais**.
- As oito linhas de tarifa originalmente invertidas passam a **sete entidades** após deduplicação; permanecem preservadas e fora dos comparativos.
- **200 distribuições de VET** preservadas; outras **560 cotações online** separadas no modelo.
- Marts de taxas passaram de 41 para **84 linhas** ao separar modalidades; tarifas passaram de 38 para **455 linhas** ao separar códigos e serviços. Esse aumento representa mudança de grão, não aumento de oferta na origem.
- Build integral anterior desta revisão: 8,046 s. Build com 169 hits silver após ajuste dos marts: 3,745 s. São medições locais distintas, não SLA.
- Navegador local: visão executiva, filtros de modalidade e família, exportação real de tarifas da família Contas, visão de câmbio/VET e ausência de erros de console nas telas inspecionadas.

## Publicação e reprodução

O repositório contém código, testes, documentação, configuração, workflows e o ZIP do snapshot público com checksum. Os diretórios de runtime `data/`, `dist/` e o ambiente virtual são regenerados e ficam fora do Git.

GitHub Actions reconstrói o resultado a partir do ZIP antes do deploy. Os relatórios de CI e deploy no GitHub identificam a revisão exata validada em Linux/Windows e o artefato publicado.

## Limites que permanecem explícitos

Docker não foi executado localmente: o daemon Docker Desktop estava indisponível. Homologação integral de impressão/PDF, leitor de tela, operação corporativa contínua, SSO, alertas, retenção automática e carga distribuída continuam fora da validação executada. A publicação atual é um único snapshot; não existe série histórica. As evoluções condicionais M01–M04 do plano permanecem um roteiro, com as melhorias já implementadas descritas acima.
