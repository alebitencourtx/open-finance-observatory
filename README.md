# Observatory · Open Finance Brasil

Engenharia de dados e inteligência executiva sobre as APIs públicas de Santander, Itaú Unibanco e Bradesco. Python, Arrow, Parquet e DuckDB; interface estática sem CDN.

- **[Dashboard executivo](https://alebitencourtx.github.io/open-finance-observatory/)**
- **[Documentação funcional e técnica — HTML único](https://alebitencourtx.github.io/open-finance-observatory/documentacao.html)**
- [Plano de revisão](PLAN.md) e [correções da versão 1.2.0](docs/correcoes-1.2.0.md).

O dashboard usa o instantâneo real de **10/11/2026**, disponibilizado em `datasets/`. Não há dados de clientes, consentimentos ou pagamentos. Dados de mercado publicados não representam taxas negociadas ou participação de mercado.

## Executar localmente

Python 3.11 ou 3.12, 64 bits. No Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m zipfile -e datasets/bronze-2026-11-10.zip data/replay-source
.\.venv\Scripts\python.exe -m observatory.cli import data/replay-source
.\.venv\Scripts\python.exe -m observatory.cli verify
.\.venv\Scripts\python.exe -m observatory.cli build
.\.venv\Scripts\python.exe -m observatory.cli serve
```

Abra `http://127.0.0.1:8765`. Também é possível abrir `dist/index.html` diretamente. O dashboard aponta para uma release completa com dados e documentação locais. Em Linux/macOS, substitua o executável por `.venv/bin/python`.

```powershell
.\.venv\Scripts\python.exe -m observatory.cli docs --output docs/documentacao.html
.\.venv\Scripts\python.exe -m pytest -q
node --check src/observatory/web/app.js
```

O HTML de documentação pode ser distribuído sozinho: estilos, scripts e três diagramas SVG estão embutidos. Links de referência são opcionais.

## Nova coleta

```powershell
.\.venv\Scripts\python.exe -m observatory.cli discover
.\.venv\Scripts\python.exe -m observatory.cli collect --concurrency 8 --per-host 2 --interval 0.25
.\.venv\Scripts\python.exe -m observatory.cli verify
.\.venv\Scripts\python.exe -m observatory.cli build --memory 1GB --threads 4
```

Retome com `collect --resume <snapshot_id>`. O parâmetro global `--lake <pasta>` vem antes do subcomando. A configuração de perímetro está em `config/groups.json`; vínculo operacional por CNPJ/domínio não comprova controle societário.

## Organização e engenharia

| Diretório | Conteúdo |
|---|---|
| `src/observatory/` | Coleta, contratos analíticos, normalização, armazenamento, CLI e apresentação |
| `src/observatory/sql/` | Definições únicas de métricas |
| `tests/` | Contratos, integração, falhas HTTP, recuperação e regressões |
| `config/` | Perímetro dos grupos |
| `datasets/` | Snapshot público comprimido e checksum para reprodução |
| `docs/` | Manual autocontido, arquitetura, operação e evidências |
| `.github/workflows/` | CI Windows/Linux e publicação GitHub Pages |
| `data/` | Lake gerado: bronze, silver, gold e manifestos; fora do Git |
| `dist/` | Publicação local gerada; fora do Git |

A coleta usa TLS verificado, concorrência limitada por host, retry e checkpoints. O bronze preserva os bytes por SHA-256. A normalização escreve lotes Arrow em Parquet Zstandard. O cache separa conteúdo de metadados de captura e verifica checksums. O build verifica bronze e integridade dos artefatos reutilizados, executa gates analíticos e prepara uma release imutável antes de substituir atomicamente a entrada do dashboard.

A transformação 1.2.0 corrige identidade de tarifas, faixas inválidas, nomenclatura de adiantamento a depositantes, paginação, retomada e preservação das distribuições de VET. Contratos analíticos mínimos não substituem validação regulatória integral de OpenAPI.

## Oito visões

Visão executiva, cobertura, portfólio, taxas e tarifas, rede, câmbio/VET, qualidade e metodologia. Taxas são separadas por modalidade, segmento, unidade e indexador. Tarifas são separadas por código/serviço/moeda; exportação inclui ambos os conjuntos. Indicadores de qualidade são técnicos e exibem ocorrências da origem.

## GitHub Pages

Em **Actions → Atualizar dados e publicar Pages → Run workflow**, mantenha **Coletar dados novos das APIs** marcado para executar todo o ETL remotamente. Desmarque para republicar a extração atual sem nova coleta. Nenhum agendamento foi criado.

O workflow mantém somente **atual + anterior** em GitHub Releases. A candidata passa pelos gates antes do deploy; só é confirmada após o Pages publicar. Uma coleta reprovada preserva o último resultado aprovado. Push em `main` testa e republica a extração aprovada, sem disparar coleta remota involuntária.

Veja [operação remota e recuperação](docs/atualizacao-remota.md). O ZIP de demonstração em `datasets/` permite o bootstrap inicial; as próximas republicações restauram os dados de Releases. Nenhuma credencial pessoal adicional é necessária: o Actions usa o token temporário do próprio repositório.

O CI também testa Windows/Linux e Python 3.11/3.12. A imagem Docker é uma opção de execução em lote; operação contínua, autenticação corporativa e observabilidade remota precisam de infraestrutura própria.

## Fontes e limites

[Confluence oficial](https://openfinancebrasil.atlassian.net/wiki/pages/viewpage.action?pageId=182845448), [Diretório de participantes](https://data.directory.openbankingbrasil.org.br/participants) e [especificações oficiais](https://github.com/OpenBanking-Brasil/openapi).

A solução é single node e tem um escritor por lake. A publicação atual é um instantâneo, sem série histórica. Valores de VET preservam a distribuição por faixas; não são convertidos em uma cotação única. As fontes públicas conservam seus direitos e condições de uso. O projeto original foi utilizado somente para leitura e permaneceu separado desta implementação.
