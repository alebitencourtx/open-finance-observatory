# Atualização remota e retenção: atual + anterior

No GitHub, abra **Actions → Atualizar dados e publicar Pages → Run workflow**.

- **Coletar dados novos das APIs marcado:** executa descoberta, coleta HTTPS, integridade, normalização, DuckDB, validação, geração e deploy.
- **Desmarcado:** republica a extração aprovada mais recente com o código atual, sem consultar os bancos.
- Push em `main` executa a republicação e os testes. Não provoca coleta nova involuntária.
- Nenhum agendamento foi criado. A execução manual ocorre nos runners padrão do GitHub, sem depender do computador do usuário.

## Armazenamento

Os dados operacionais ficam em **Releases**, com tags iniciadas por `extraction-`. Cada pacote `snapshot.zip` contém apenas os objetos bronze referenciados e o manifesto do snapshot. `SHA256SUMS` protege o pacote; os hashes internos são conferidos ao restaurar. DuckDB, silver, marts e site são reconstruídos e não precisam permanecer em disco entre execuções.

São mantidas as **duas últimas extrações aprovadas**: atual e anterior. Na primeira execução existe somente a atual; a anterior surge na próxima atualização aprovada. A ordenação usa a publicação dos pacotes, não a data do commit referenciado pela tag.

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
