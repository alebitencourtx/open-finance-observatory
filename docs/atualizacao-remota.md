# Atualização remota e retenção: atual + anterior

Guia operacional revisado em 10/11/2026. A [documentação HTML completa](https://alebitencourtx.github.io/open-finance-observatory/documentacao.html) contém comandos de restauração em outro lake, dicionários, diagramas e cópias dos arquivos operacionais. Este guia descreve o OpenData; o cron de duas horas pertence ao projeto Admin Metrics.

No GitHub, abra **Actions → Atualizar dados e publicar Pages → Run workflow**.

- **Coletar dados novos das APIs marcado:** executa descoberta, coleta HTTPS, integridade, normalização, DuckDB, validação, geração e deploy.
- **Desmarcado:** republica a extração aprovada mais recente com o código atual, sem consultar os bancos.
- Push em `main` executa a republicação e os testes. Não provoca coleta nova involuntária.
- Nenhum agendamento foi criado. A execução manual ocorre nos runners padrão do GitHub, sem depender do computador do usuário.

## Armazenamento

Os dados operacionais ficam em **Releases**, com tags iniciadas por `extraction-`. Cada pacote `snapshot.zip` contém apenas os objetos bronze referenciados e o manifesto do snapshot. `SHA256SUMS` protege o pacote; os hashes internos são conferidos ao restaurar. DuckDB, silver, marts e site são reconstruídos e não precisam permanecer em disco entre execuções.

A retenção automática vale para Releases, não limpa o lake local e não cria série histórica no dashboard. São mantidas as **duas últimas extrações aprovadas**: atual e anterior. Na primeira execução existe somente a atual; a anterior surge na próxima atualização aprovada. A ordenação usa a publicação dos pacotes, não a data do commit referenciado pela tag.

O ZIP em `datasets/` é o exemplo original fixo para reprodução e bootstrap inicial. Ele não é usado para substituir silenciosamente uma extração remota quando um download falha. Após a primeira aprovação remota, as republicações usam o pacote atual de Releases.

## Proteção de publicação

1. Restaura a extração atual e prepara a candidata em outro lake.
2. Verifica bronze e executa os gates analíticos existentes.
3. Exige os três grupos, produtos e pontos físicos em todos, pelo menos 90% de coleta completa em cada grupo e nenhuma queda superior a 10% em endpoints, ofertas ou rede em relação à atual.
4. Gera site e documentação completos. Só depois prepara um pacote temporário em draft.
5. Publica o artefato no Pages.
6. Confirma a candidata em Releases e conserva atual + anterior. A limpeza alcança apenas tags `extraction-`, nunca versões de código ou outras releases.

Falha anterior ao deploy preserva o site e os dois pacotes aprovados. Um draft temporário é descartado em falhas tratadas do workflow. Se houver cancelamento abrupto, pode restar um draft; ele não é selecionado como atual e deve ser inspecionado antes de remoção.

Pages e Releases não têm uma transação conjunta. Se o deploy concluir e a confirmação em Releases falhar, o job fica vermelho: reexecute o workflow completo e investigue o log. Nunca se elimina a anterior antes de confirmar a nova. Gates não devem ser afrouxados para contornar indisponibilidade da fonte.

## Recuperação

Os pacotes publicados podem ser baixados em **Releases**. Para recuperar uma falha transitória de execução, use **Re-run all jobs**. Os logs do Actions mostram erro por endpoint e o gate que impediu a atualização. Uma execução reprovada não conta como nova extração aprovada.

Não existe atualização contínua nem promessa de horário exato. Se um agendamento for adicionado no futuro, terá as mesmas validações e retenção e deverá compartilhar a exclusão mútua do deploy.

## Contratos observados na coleta remota

A cadeia pública ICP-Brasil v10 é carregada somente pelo transporte de api.bradesco.com, com raiz obtida por HTTPS do ITI e fingerprint fixado. Os demais hosts usam a loja padrão. Não há fallback sem validação TLS.

Totais de registros são reconciliados com os grãos presentes na resposta (envelopes, produtos, correspondentes ou locais); o manifesto registra as contagens e os grãos correspondentes ao total informado. Os indicadores de registros de origem continuam usando envelopes de primeiro nível.

A rota exata `https://api.itau/open-banking/channels/v2/branches` publica `meta.totalRecords` como quantidade **da página**, embora existam várias páginas. Esse adaptador valida cada contagem de página e percorre `totalPages`; registra `reported_total_scope=page`. Não se aplica essa exceção a outros hosts/rotas. Divergências de contagem continuam sendo erros. O grão observado foi conferido em respostas reais de páginas distintas em 10/11/2026; isso não implica conformidade regulatória da origem.

## Identificadores e promoção

O código do deploy, a versão de transformação, o snapshot dos dados, o build analítico e a revisão documental são identidades diferentes. Uma republicação pode mudar build e assets sem mudar snapshot ou janela da coleta. `site/publication.json` registra os gates, snapshot e origem aprovados.

No OpenData, `promote` confia na ordem do workflow: o job deploy deve ter sucesso antes da chamada. O helper isolado não verifica um recibo remoto de deploy. Não execute promoção manual de candidata sem comprovar a publicação. O protocolo do Admin Metrics verifica explicitamente o job e grava recibo; não trate os dois helpers como equivalentes.

## Atualizar apenas a documentação

Edite os templates e o gerador, regenere `docs/documentacao.html` a partir da extração aprovada e revise os testes e o diff. Commit/push republica sem coleta. Confira build/deploy aprovados, raiz do site e URL estável `documentacao.html`. O exemplo em `datasets/` continua fixo para reprodução e não deve ser apresentado como a extração remota mais recente.
