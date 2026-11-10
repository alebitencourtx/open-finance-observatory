# Definições e reconciliação

O manual principal é [documentacao.html](documentacao.html), completo e autocontido. Esta nota acompanha as regras no repositório.

As métricas são definidas em `src/observatory/sql/marts.sql`. As definições abaixo pertencem à transformação **1.2.0**.

| Conceito | Regra |
|---|---|
| Oferta | Conteúdo distinto de produto por empresa/família; inclui sociedade em produtos aninhados |
| Endpoint | Identidade de grupo, CNPJ, família e URL |
| Presença | Registros > 0 e HTTP final 200 |
| Completude | HTTP 200 sem erro ou truncamento |
| Cobertura do escopo | Famílias com presença / 14 |
| Cobertura declarada | Famílias com presença / famílias do catálogo |
| Rede física | Agências + ATMs + correspondentes; sem exclusividade entre empresas |
| Índice técnico | Média dos quatro componentes disponíveis: completude, presença, UF física, taxa válida de crédito |

O valor decimal da API é convertido por multiplicação por 100. Não há inferência de escala por magnitude. Para crédito pré-fixado usa-se `minimumRate`; para percentual pós-fixado usa-se `rate`. Os campos `minimumRate` e `maximumRate` de uma observação pós-fixada são preservados em `effective_minimum` e `effective_maximum`, sem serem tratados como percentual do indexador. As medianas por faixa de `applications.indexer.rate` não substituem mínimos ausentes ou zerados.

Referência: [LoanInterestRate e ApplicationRate da especificação oficial 1.1.0](https://github.com/OpenBanking-Brasil/api-opendata-loans/blob/main/swagger.yaml).

Pré-fixadas aceitas têm mínimo positivo ≤ 50%; fatores pós-fixados têm valor positivo ≤ 300%. Faixas invertidas e unidades desconhecidas são excluídas. Os limites são critérios analíticos, não regras de validação regulatória. Cada oferta contribui uma observação por indexador; as distribuições são separadas por segmento/unidade/indexador, sem ponderação por volume.

Os números do README antigo não são baseline de igualdade: lá produtos eram nomes únicos por grupo; aqui são ofertas por conteúdo. O total de registros de primeiro nível também fica separado de produtos e locais expandidos. O índice antigo usava nomes de produtos e todos os canais no componente geográfico; aqui usa identidades e apenas pontos físicos.

Na versão 1.2.0, taxas são agrupadas também por modalidade. Tarifas são separadas por código e serviço, com exclusão explícita de faixas inválidas. Adiantamento a depositantes é a denominação de unarranged; cheque especial permanece uma modalidade de loans. VET conserva distribuição e faixa, separadamente de cotação online.
