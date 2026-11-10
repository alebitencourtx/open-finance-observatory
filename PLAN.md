# Plano de revisão e evolução — Observatory

**Data:** 10/11/2026 · **Situação:** correções B01–B13 aplicadas na transformação 1.2.0; ver relatório de execução.

Este documento compara o pedido original com a entrega, registra os problemas encontrados e organiza as próximas ações. Foi produzido a pedido do usuário, sem modificar o código da aplicação ou o projeto original.

## 1. Parecer sobre a entrega

A entrega tem uma base local funcional, uma organização mais clara e escolhas de processamento coerentes com o volume observado. Arrow, Parquet e DuckDB podem ser mantidos. O dashboard e o manual têm identidade visual consistente e permitem explorar dados reais com rastreabilidade.

Entretanto, a entrega ainda precisa de correções de confiabilidade e semântica antes de sustentar uma apresentação executiva com confiança. Há problemas reproduzidos de publicação, recuperação, normalização e agregação. A aprovação dos 38 testes existentes não cobre esses cenários.

**Recomendação:** corrigir os fundamentos e aprofundar o produto existente. Uma nova reconstrução completa ou a introdução imediata de infraestrutura distribuída não se justifica pelas evidências desta revisão.

## 2. Pedido original × resultado

| Pedido | Resultado observado | Avaliação |
|---|---|---|
| Preservar o projeto original | Implementação em outra pasta; importação dos bytes de origem | Atendido no trabalho realizado. Nesta revisão, 169 objetos continuam iguais aos arquivos de origem |
| Melhorar organização | Módulos separados para armazenamento, coleta, normalização, marts, apresentação e CLI | Atendido como base; faltam contratos e adaptadores mais específicos por família e versão |
| ETL performático | Processamento em lotes, Parquet, SQL vetorizado e concorrência limitada | Boa base. O cache entre coletas tem um problema; falta benchmark recorrente e de memória |
| Práticas avançadas de engenharia de dados | Bronze endereçado por hash, versionamento, checkpoints, gates e testes | Parcial. Publicação, recuperação, validação de contratos e integridade de cache precisam de reforço |
| Dashboard executivo | Sete visões, filtros, detalhes, exportação e apresentação visual consistente | Parcial. A semântica de alguns indicadores precisa de correção; a leitura ainda privilegia inventário e qualidade técnica |
| Documentação funcional e técnica única | HTML com CSS/JS/SVG embutidos, busca, schemas, código e operação | Atendido na forma; conteúdo estático pode ficar incorreto em novas gerações |
| Desenhos de solução, fluxo e ER | Três diagramas SVG ampliáveis | Atendido; atualizar junto das correções de arquitetura e modelo |

O README original consultado descreve um pipeline de descoberta, extração, silver, gold, qualidade e relatório para Santander, Itaú e Bradesco. A comparação funcional deve preservar esse perímetro e explicar diferenças de granularidade, sem exigir que métricas calculadas por regras distintas tenham números idênticos.

## 3. Evidências e limites desta revisão

- Leitura do README e do histórico de revisão do projeto original, sem executar seu código.
- Revisão do código Python, SQL, JavaScript, templates, documentação, configuração e testes da nova versão.
- Consultas ao warehouse com conexão somente leitura.
- Inspeção das prévias visuais já existentes do dashboard e do manual. Não houve nova homologação interativa completa de navegador nesta revisão.
- Execução da suíte existente: **38 testes aprovados em 3,11 segundos**; cache do pytest desabilitado.
- Verificação sintática de `app.js` aprovada.
- Verificação dos **169 objetos bronze** aprovada; comparação com a origem: **zero divergências**.
- Reprodução de cenários de falha em diretórios temporários e transporte HTTP simulado. Nenhuma dessas simulações alterou o lake ou os artefatos publicados do projeto.
- Consulta às especificações oficiais para conferir nomenclatura e estrutura de dados. Não foi feita nova coleta integral dos bancos.

**Base analisada:** snapshot `import-5085591ce24039e73119`, build `b382f6e22f3ddca667c73b4e`, transformação `1.1.1`.

O tempo de 12,433 segundos para processamento de aproximadamente 146 MB é evidência da entrega anterior, registrada na documentação. Não foi repetido como benchmark nesta revisão.

**Classificação:** P1 = corrigir antes de homologar a solução para uso executivo ou operação recorrente; P2 = corrigir na consolidação da próxima versão. “Reproduzido” significa cenário executado; “observado” significa encontrado na base real ou demonstrável diretamente pelo código. Melhorias de produto estão separadas dos bugs.

## 4. Bugs e riscos confirmados

### B01 · P1 — A publicação do dashboard não é atômica como conjunto

**Evidência:** [build.py:132](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/build.py:132). `render_dashboard` copia os assets e substitui os dados antes de gerar o manual. O ponteiro `latest.json` não controla a pasta estática que o usuário abre.

**Reprodução:** ao provocar falha na geração do manual, o ponteiro permaneceu no build anterior, mas `dist/data.js` já continha os dados novos e `dist/manual.html` continuava antigo.

**Impacto:** uma execução que falha pode deixar o dashboard publicado com arquivos de versões diferentes. A proteção do ponteiro, isoladamente, não preserva a experiência anterior.

**Ação:** preparar e validar uma versão completa em destino separado; publicar por uma referência única para a versão concluída. Definir a estratégia compatível com Windows e com o modo offline, sem presumir que várias substituições de arquivo formam uma transação. Considerar também colisão de dois lakes publicando no mesmo destino.

**Aceite:** falhas injetadas em cada etapa de renderização mantêm a versão anterior integralmente utilizável. HTML, dados, assets e manual publicados identificam a mesma versão. Rollback restaura o conjunto completo.

### B02 · P1 — Retomada não fecha snapshot após o último checkpoint

**Evidência:** [collect.py:233](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/collect.py:233). A retomada retorna imediatamente quando não há endpoints pendentes.

**Reprodução:** manifesto com todos os endpoints concluídos, mas ainda em `collecting`, retornou com o mesmo estado, sem fingerprint e sem publicação em `latest-bronze.json`.

**Impacto:** queda entre o último checkpoint e o fechamento deixa uma coleta completa impedida de seguir para o build.

**Ação:** separar execução de endpoints e finalização idempotente do snapshot. A ausência de pendências deve permitir finalizar uma coleta aberta; um snapshot já fechado deve continuar preservado.

**Aceite:** interromper antes e depois do último checkpoint e retomar produz um snapshot fechado e verificável, sem novas requisições para endpoints já completos.

### B03 · P1 — Contratos permissivos permitem dados inválidos e perdas silenciosas

**Evidência:** [normalize.py:172](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/normalize.py:172). A validação verifica principalmente se o registro é um objeto. Elementos inválidos de produtos aninhados e locais podem ser ignorados.

**Reprodução:** `{}` em uma família de empréstimos gerou um produto sem quarentena. Uma lista `society.products` com um número e um produto válido descartou o número silenciosamente.

**Impacto:** “quarentena vazia” não demonstra aderência ao contrato da API. Contagens podem crescer com registros sem conteúdo ou cair por descarte não contabilizado.

**Ação:** definir contratos por família, rota e versão; validar campos necessários para cada análise. Preservar divergências com caminho JSON e motivo. Distinguir compatibilidade analítica de conformidade integral com OpenAPI, sem atribuir ao gate uma garantia que ele não oferece.

**Aceite:** cada registro ou elemento relevante tem destino contabilizado: aceito, rejeitado ou explicitamente fora do escopo. Alterações de schema e elementos aninhados inválidos não desaparecem sem evidência.

### B04 · P1 — Paginação pode declarar sucesso incorreto ou escapar do tratamento de erro

**Evidência:** [collect.py:202](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/collect.py:202).

**Reproduções:**

- Dois registros recebidos, `totalRecords=1` e uma página: captura terminou sem erro.
- Página inicial vazia com `totalPages=3`: captura terminou sem erro.
- `meta` como lista não vazia: ocorreu `AttributeError` fora do tratamento de falha da captura.

**Impacto:** a completude pode ser superestimada; um payload malformado pode interromper a execução do conjunto em vez de produzir uma ocorrência isolada do endpoint.

**Ação:** validar tipo e coerência de metadados; distinguir ausência de totais de totais declarados; estabelecer regras para divergências em ambas as direções e mudanças durante a paginação. Tratar erro de contrato na fronteira da captura, preservando o corpo e os checkpoints. Não mascarar erros internos indiscriminadamente.

**Aceite:** os três cenários acima ficam explicitamente incompletos ou rejeitados, com motivo e evidência; outros endpoints podem concluir. Cobrir também totais negativos, não inteiros e inconsistentes entre páginas.

### B05 · P1 — Deduplicação de produtos não se propaga corretamente a tarifas

**Evidência:** [normalize.py:105](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/normalize.py:105). A identidade da tarifa inclui o caminho absoluto no JSON, enquanto o produto é identificado por conteúdo.

**Reprodução:** dois produtos idênticos em posições distintas resultaram em um produto e duas tarifas, sem deduplicação dessas tarifas.

**Base real:** a oferta `1538fcaefb81e88e2275eea12ff335ea` aparece em `$.data[2]` e `$.data[7]` do mesmo objeto bronze; a tarifa associada permanece repetida no warehouse.

**Impacto:** itens de tarifa e distribuições podem receber peso adicional por repetição de publicação. A mesma construção de identidade também merece revisão nas observações de taxa.

**Ação:** separar identidade da entidade de localização da evidência; usar contexto do serviço dentro da oferta e preservar todas as proveniências em relação própria. Não eliminar indiscriminadamente serviços com nome e valor iguais: podem pertencer a pacotes ou condições distintos.

**Aceite:** repetir ou mover a mesma oferta entre posições e páginas não altera indicadores. Serviços legitimamente diferentes preservam contexto e continuam distintos. Auditar e reconciliar o efeito na base real.

### B06 · P1 — Tarifas com faixa invertida entram nas métricas

**Evidência:** [marts.sql:43](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/sql/marts.sql:43) agrega tarifas sem filtro de validade. A tabela de tarifas não possui classificação equivalente à das taxas.

**Base real:** **oito linhas** têm `maximum < minimum`. Exemplo: mínimo de R$ 1.000,81 e máximo de R$ 994,85. Essas oito linhas incluem repetição; não representam necessariamente oito problemas únicos de origem.

**Impacto:** valores inconsistentes participam dos resumos executivos sem aviso específico.

**Ação:** preservar valor publicado e adicionar validade, motivo, unidade monetária e contexto. Excluir valores inconsistentes dos comparativos conforme política explícita e mostrar as exclusões. Revisar uso de decimal para valores monetários.

**Aceite:** faixas invertidas, valores negativos e moeda ausente/inconsistente são tratados de forma testada. Zero válido permanece zero. O painel mostra denominadores e exclusões de tarifas.

### B07 · P1 — “Adiantamento a depositantes” está rotulado como “Cheque especial”

**Evidência:** [domain.py:7](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/domain.py:7) associa `unarranged` a “Cheque especial”. A regra também é repetida nas famílias de crédito do SQL.

**Base real:** seis ofertas da família `unarranged`, duas por conglomerado, recebem esse rótulo.

**Referência:** a especificação de [OpenData Unarranged](https://raw.githubusercontent.com/OpenBanking-Brasil/api-opendata-unarranged/main/swagger.yaml) descreve adiantamento a depositantes. A modalidade de cheque especial aparece na especificação de [OpenData Loans](https://raw.githubusercontent.com/OpenBanking-Brasil/api-opendata-loans/main/swagger.yaml).

**Impacto:** a nomenclatura induz interpretação incorreta da família e da comparação de taxas.

**Ação:** corrigir a taxonomia, regras SQL, filtros, textos e documentação; versionar a mudança e reprocessar a base.

**Aceite:** família e modalidade têm correspondência explícita com a fonte; o mesmo termo não representa produtos distintos por erro de mapeamento.

### B08 · P1 — Normalização de câmbio perde o conteúdo de VET

**Evidência:** [normalize.py:188](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/normalize.py:188) aplica uma estrutura genérica às rotas de câmbio.

**Base real:** existem 760 registros em `exchange`: 560 de `online-rates`, com valor, e **200 de `vet-values`, todos com `value` nulo**. O bronze desses 200 registros contém `vetAmount`, com mínimos, máximos e faixas. O schema também não preserva campos como tipo de operação e forma de entrega.

**Impacto:** há perda na representação analítica, embora o bronze permita recuperação. O dado disponível não pode ser interpretado corretamente só pela tabela produzida. Câmbio também não possui mart de consumo nem visão específica no dashboard entregue.

**Ação:** criar adaptações e contratos distintos para taxa online e VET, preservando operação, moeda, entrega, público, faixa de valor, distribuição e referência temporal aplicável. Definir o consumo executivo ou declarar claramente o limite de escopo.

**Aceite:** os 200 registros são representados sem inventar um valor único a partir de uma distribuição. Reconciliação comprova correspondência entre valores bronze e tabelas analíticas. A especificação oficial de [OpenData Exchange](https://raw.githubusercontent.com/OpenBanking-Brasil/api-opendata-exchange/main/swagger.yaml) distingue essas duas estruturas.

### B09 · P2 — Faixas efetivas invertidas de pós-fixados não são sinalizadas

**Evidência:** [normalize.py:118](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/normalize.py:118). O normalizador preserva a faixa efetiva, mas substitui mínimo e máximo pelo fator do indexador antes da validação de inversão.

**Reprodução:** pós-fixado com fator de 100%, mínimo efetivo de 4% e máximo efetivo de 1% foi marcado como válido, sem motivo de exclusão.

**Limite:** a consulta à base real não encontrou esse cenário entre os pós-fixados válidos atuais.

**Ação:** validar fator e faixa efetiva como dimensões distintas. Definir se um fator válido pode continuar comparável com ressalva quando a faixa efetiva é inválida; alinhar a documentação a essa decisão.

**Aceite:** nenhuma inversão efetiva passa sem diagnóstico. A decisão de inclusão no comparativo é explícita e testada.

### B10 · P2 — Cache não reaproveita adequadamente conteúdo igual entre novas coletas

**Evidência:** [normalize.py:210](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/normalize.py:210). A chave inclui toda a captura: data, latência e outros metadados voláteis.

**Verificação:** alterar somente `captured_at`, mantendo os mesmos objetos, muda a chave do cache.

**Impacto:** o reaproveitamento funciona no replay da mesma captura, mas tende a falhar entre coletas novas com conteúdo idêntico. A documentação promete um benefício mais amplo do que a chave entrega.

**Ação:** separar cache da transformação de conteúdo da materialização de metadados da captura. Incluir identidade semântica e versão necessárias, sem reutilizar datas ou status antigos por engano.

**Aceite:** duas coletas com payload idêntico reaproveitam a transformação; data, status e linhagem continuam correspondendo à captura correta. Medir tempo e taxa de acerto em replay, coleta inalterada e alteração parcial.

### B11 · P2 — Reutilização de build/cache não verifica sua integridade

**Evidência:** [build.py:53](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/build.py:53) e [normalize.py:213](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/normalize.py:213). Marcadores de conclusão bastam para aceitar resultados existentes.

**Reprodução:** corromper um bronze em lake temporário não impediu a reutilização do build concluído; `verify` detectou a corrupção quando executado separadamente.

**Impacto:** não há prova automática de integridade da cadeia ao executar somente `build`. O comando `verify` cobre bronze, mas não verifica hashes dos artefatos silver/gold ou sua correspondência com o marcador.

**Ação:** definir política explícita de verificação antes da publicação; registrar hashes, tamanhos, contratos e versões dos artefatos. Integrar a verificação ao fluxo operacional e oferecer auditoria completa, com custo mensurado.

**Aceite:** objetos corrompidos, Parquet ausente/alterado e marcadores inconsistentes são detectados antes de republicar. A recuperação não aceita silenciosamente cache inválido.

### B12 · P2 — Exportação de “Taxas e tarifas” omite tarifas

**Evidência:** [app.js:186](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/web/app.js:186). Para essa visão, `exportData()` usa somente `rateRows()`, embora a tela também mostre `fees_family`.

**Base real:** Contas e Adquirência possuem tarifas agregadas e não possuem linhas em `rates_family`. Nesses recortes, o botão pode informar ausência de registros mesmo com tarifas visíveis.

**Ação:** oferecer exportação identificada de taxas e de tarifas, ou formato que preserve os dois conjuntos sem misturar schemas. Incluir contexto dos filtros, snapshot e unidades.

**Aceite:** as tarifas visíveis podem ser exportadas; os filtros são respeitados e a ausência de taxas não bloqueia exportação de tarifas.

### B13 · P2 — Manual regenerado pode conter evidência e origem desatualizadas

**Evidência:** [manual.html:25](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/templates/manual.html:25), [manual.html:119](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/templates/manual.html:119) e [documentation.py:106](C:/Users/alebi/Documents/ChatGPT/teste-opendata/src/observatory/documentation.py:106). O template contém data fixa da entrega, afirmação de replay e textos de validação histórica; o gerador atualiza apenas parte das informações.

**Impacto:** um build futuro de coleta direta pode gerar um manual com IDs e métricas novos, mas ainda declarar origem importada ou transmitir como atuais testes realizados em outra versão.

**Ação:** separar documentação de funcionamento, evidências do build e histórico de homologação. Preencher origem e datas a partir dos metadados; associar testes e benchmarks à versão em que foram executados. Versionar também código/SQL usados na geração do manual.

**Aceite:** gerar documentação para importação, coleta direta e build antigo mantém origem, datas, regras e evidências coerentes. A ausência de homologação aparece como ausência, sem herdar aprovação histórica.

## 5. Oportunidades de melhoria

### M01 — Tornar a visão executiva orientada a perguntas de decisão

A linguagem visual atual pode ser preservada. A prioridade é melhorar a leitura e a comparabilidade.

- Definir as perguntas que o painel responde: onde há lacunas de publicação, quais comparações são sustentadas e quais dados exigem investigação.
- Separar claramente amplitude de publicação, volume de ofertas e qualidade técnica. Contagem de ofertas não demonstra participação de mercado.
- Exibir amostra elegível, exclusões e cobertura ao lado dos comparativos, sem exigir consulta ao manual para entender a confiança do resultado.
- Comparar taxas por modalidade, segmento e indexador, além da família. Hoje modalidades distintas podem entrar no mesmo agregado.
- Para tarifas, comparar serviços e condições equivalentes. Na base real, Contas/PF do Itaú reúne 105 códigos e 118 nomes de serviço numa única agregação por grupo/família/segmento/moeda. Essa mediana descreve uma mistura de serviços, não uma cesta padronizada de preço.
- Mostrar limitações do índice composto e disponibilidade de seus componentes. Evitar leitura de superioridade geral do banco a partir de um indicador técnico.
- Dar acesso a condições da oferta, evidências das taxas/tarifas e motivos de exclusão a partir do comparativo.
- Se houver histórico validado no futuro, apresentar mudanças de período. Não produzir tendências a partir do instantâneo atual.

**Aceite de produto:** um leitor executivo consegue identificar o universo, a data, a pergunta respondida, a amostra e a principal limitação de cada visualização sem interpretar código ou fórmulas técnicas.

### M02 — Consolidar navegação, acessibilidade e relatório

- Validar manutenção de foco após filtros e ordenação: o código recria controles e normalmente chama `render()` sem restaurar o foco. O efeito precisa de teste interativo específico.
- Expor estado de ordenação de tabela de forma acessível e fornecer alternativa tabular para gráficos.
- Medir contraste e legibilidade, especialmente textos pequenos e secundários; testar zoom e leitor de tela.
- Rever o botão de relatório: o CSS o oculta entre 651 e 1.200 px e volta a exibi-lo em telas menores. A disponibilidade da função deve ser coerente.
- Diferenciar o escopo de filtros locais, como UF, do escopo dos gráficos nacionais na mesma página.
- Homologar impressão/PDF em A4 e modo de apresentação em tela ampla. O PDF não foi homologado na entrega anterior.
- Introduzir testes automatizados de jornadas reais: navegação, teclado, filtros combinados, exportação, detalhe e impressão.

**Aceite:** jornadas completas por teclado, sem perda de foco impeditiva; conteúdo legível em resoluções acordadas; relatório sem cortes; downloads correspondentes ao recorte apresentado.

### M03 — Evoluir operação e observabilidade sem trocar a stack por antecipação

- Criar um fluxo operacional verificável de descoberta, coleta, integridade, transformação, qualidade e publicação.
- Registrar `run_id`, versão do código, versão dos contratos, catálogo/configuração, política efetivamente usada e identificadores de artefatos.
- Na retomada, registrar mudanças de política. Hoje o manifesto pode conservar a política da execução inicial enquanto o novo `Collector` usa outros limites.
- Registrar tentativas e esperas de retry. Hoje a chamada retorna ao capturador a resposta final; as tentativas intermediárias não possuem a mesma evidência das páginas finais.
- Definir freshness, limites de publicação parcial e tratamento de desaparecimento de empresas/endpoints. Uma redução do catálogo não deve parecer automaticamente melhora de qualidade.
- Separar falha da instituição, erro de contrato e limitação do coletor nos indicadores de operação.
- Definir backup, restauração e retenção com ensaio de recuperação.
- Executar CI e Docker efetivamente antes de declará-los homologados; ampliar validação de empacotamento e instalação limpa.
- Se houver distribuição corporativa, definir hosting, identidade e responsáveis. Não presumir que o servidor local de preview atende a esse papel.

**Aceite:** uma execução pode ser rastreada, interrompida, retomada, auditada e revertida; falhas e atrasos possuem responsáveis e critérios explícitos.

### M04 — Completar governança de modelo, desempenho e documentação

- Documentar granularidade, chave de negócio, chave de conteúdo e cardinalidade de cada tabela; separar identidade estável e versão antes de introduzir histórico.
- Preservar relações de proveniência de entidades deduplicadas, em vez de depender apenas de uma origem escolhida deterministicamente.
- Fixar as versões de especificações utilizadas e registrar a regra de seleção de versões de API no catálogo.
- Incluir no manual a semântica dos campos derivados dos marts, denominadores, regras de exclusão e exemplos de interpretação.
- Atualizar ER, desenho da solução e fluxo de recuperação junto do modelo e da estratégia de publicação.
- Medir memória de pico, disco temporário, quantidade/tamanho de Parquets, tempo por etapa e tamanho/tempo de carregamento do dashboard. O JSON atual tem aproximadamente 4,83 MB.
- Avaliar o custo de pequenos arquivos e snapshots acumulados. A promessa de desempenho deve incluir coleta recorrente, não apenas um build local.
- Manter separação entre metas futuras, capacidades implementadas e evidências efetivamente executadas.

## 6. Sequência de execução proposta

### Etapa 1 — Corrigir confiança dos dados e publicação

- [ ] Resolver B01 e B02: publicação consistente e recuperação após último checkpoint.
- [ ] Resolver B03 e B04: contratos, descarte contabilizado e paginação coerente.
- [ ] Resolver B05 e B06: identidade de tarifas e exclusão de faixas inválidas.
- [ ] Resolver B07 e B08: taxonomia e contratos de câmbio.
- [ ] Adicionar testes de regressão dos cenários reproduzidos antes de encerrar cada correção.
- [ ] Incrementar a versão de transformação e executar reconciliação por conglomerado/família.

**Saída:** nenhuma falha P1 desta revisão permanece aberta; diferenças de números são explicadas por regra e evidência, preservando o snapshot anterior.

### Etapa 2 — Consolidar reprocessamento e rastreabilidade

- [ ] Resolver B09, B10 e B11.
- [ ] Registrar versões, política efetiva e proveniência necessárias à auditoria.
- [ ] Medir primeira execução, replay, coleta com conteúdo inalterado e alteração parcial.
- [ ] Ensaiar restauração e rollback com artefatos completos.

**Dependência:** contratos e identidade da etapa 1 estabilizados, para não otimizar cache sobre semântica incorreta.

### Etapa 3 — Homologar a experiência executiva

- [ ] Resolver B12 e os problemas de interação confirmados na validação de M02.
- [ ] Aplicar M01: comparativos homogêneos, amostras, exclusões e contexto de decisão.
- [ ] Definir exposição de câmbio e outras famílias que hoje aparecem principalmente em cobertura.
- [ ] Testar jornadas com todos os conglomerados e combinações relevantes de filtros.
- [ ] Homologar teclado, tamanhos de tela e relatório impresso.

**Dependência:** métricas corrigidas e reconciliadas; não estabilizar telas em torno de números que ainda vão mudar por bugs conhecidos.

### Etapa 4 — Fechar documentação e prontidão operacional

- [ ] Resolver B13 e sincronizar os três diagramas com a implementação final.
- [ ] Atualizar dicionário, regras, integrações, stack e justificativas no HTML único.
- [ ] Executar CI, instalação limpa e validação de Docker conforme o modo de distribuição escolhido.
- [ ] Registrar evidências de homologação ligadas à versão final.
- [ ] Definir operação recorrente e publicação corporativa apenas conforme o uso acordado.

**Saída:** manual autocontido consistente com os artefatos, instruções reproduzíveis e limites operacionais explícitos.

## 7. Critérios de encerramento

- [ ] Projeto original permanece preservado.
- [ ] Todos os P1 corrigidos e os P2 tratados ou registrados com justificativa específica.
- [ ] Testes existentes e novas regressões passam; quantidade de testes não é usada como substituto de cobertura de cenários.
- [ ] Falha em publicação mantém o resultado anterior integralmente utilizável.
- [ ] Retomada funciona nos pontos críticos de interrupção.
- [ ] Dados inválidos e descartes possuem contagem, origem e motivo.
- [ ] Métricas corrigidas são reconciliadas com o bronze e explicadas no manual.
- [ ] Taxas e tarifas comparam unidades e contextos coerentes; exclusões ficam visíveis.
- [ ] Desempenho é medido com procedimento reproduzível, incluindo memória e reutilização entre capturas.
- [ ] Dashboard, dados e documentação pertencem à mesma publicação.
- [ ] Jornadas executivas, exportação, teclado e impressão estão homologados.
- [ ] Documento HTML continua único e independente de assets externos de execução.

## 8. Limites deste plano

Este plano não declara a existência de corrupção na base atual: os hashes conferiram. Também não atribui aos bancos os defeitos introduzidos pelo processamento. As simulações isoladas demonstram cenários que o código atual não trata corretamente; os achados na base real estão identificados separadamente.

Não foi realizada auditoria integral de segurança, homologação regulatória, nova coleta de todos os endpoints ou medição de desempenho em outras máquinas. O plano não exige migração para Spark, Kafka, Kubernetes, outro framework de frontend ou nuvem sem requisito e medição que a justifiquem.

**Histórico:** este plano foi inicialmente produzido sem alterações de código. As correções foram autorizadas posteriormente e estão registradas em `docs/correcoes-1.2.0.md`. As melhorias de infraestrutura e homologação corporativa permanecem condicionadas ao uso previsto.
