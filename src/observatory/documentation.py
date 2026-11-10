"""Generate one self-contained functional/technical HTML from actual contracts and build evidence."""
from __future__ import annotations

import ast
import html
import json
from pathlib import Path

import duckdb

from .domain import SCHEMAS
from .storage import atomic_write, read_json

HERE = Path(__file__).parent


def escape(value):
    return html.escape(str(value if value is not None else "—"))


def number(value):
    return f"{value:,}".replace(",", ".")


def table(headers, data):
    return '<div class="table-scroll"><table><thead><tr>' + ''.join(f'<th>{escape(h)}</th>' for h in headers) + \
        '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{escape(v)}</td>' for v in row) + '</tr>' for row in data) + '</tbody></table></div>'


FIELD_HELP = {
    "transaction_type": "Compra ou venda publicada; dimensão independente da moeda.",
    "delivery": "Forma de entrega da moeda estrangeira publicada pela instituição.",
    "range_category": "Faixa de valor de operação utilizada na distribuição VET.",
    "vet_minimum": "Valor mínimo de VET publicado; não substitui cotação online.",
    "vet_maximum": "Valor máximo de VET publicado.",
    "vet_prices": "JSON da distribuição original de VET por faixa, mediana e proporção de operações.",
    "group_id": "Identificador operacional do conglomerado; sem prova de controle societário.",
    "company": "Nome da empresa no catálogo de origem.", "cnpj": "CNPJ da empresa do catálogo; string para preservar zeros.",
    "family": "Código original da família/rota Open Finance.", "family_label": "Domínio analítico padronizado.",
    "segment": "PF/PJ quando informado pela rota; NA nos demais casos.",
    "endpoint_id": "SHA-256 de grupo, CNPJ, família e URL; FK lógica para endpoints.",
    "source_sha": "SHA-256 do objeto bronze que contém a evidência original.",
    "entity_id": "Identidade técnica por conteúdo, empresa e família; deduplicação determinística.",
    "product_id": "FK lógica para products.entity_id.", "name": "Nome publicado ou derivado de tipo/emissor.",
    "indexer": "Indexador declarado; preservado sem misturar CDI, Selic ou outros.",
    "unit": "pct_month, pct_indexer ou unknown; controla a comparabilidade.",
    "minimum": "Mínimo pré-fixado, fator pós-fixado em %, ou mínimo monetário, conforme a tabela/unidade.",
    "maximum": "Máximo pré-fixado, fator pós-fixado em %, ou máximo monetário, conforme a tabela/unidade.",
    "effective_minimum": "minimumRate original × 100, preservado separadamente do percentual do indexador.",
    "effective_maximum": "maximumRate original × 100, preservado separadamente do percentual do indexador.",
    "raw_minimum": "Valor textual que originou minimum; para pós-fixado vem do campo rate.",
    "raw_maximum": "Valor textual que originou maximum.", "json_path": "Caminho do campo ou nó no JSON bronze.",
    "valid": "Elegível para as métricas analíticas, segundo unidade, valor e faixa.",
    "reason": "Motivo de exclusão/quarentena; string vazia em taxa válida.",
    "raw_json": "Registro rejeitado preservado para investigação.", "status": "Último HTTP da captura; 0 em falha sem resposta.",
    "records": "Registros de primeiro nível no array data; não é total de locais ou produtos aninhados.",
    "pages": "Páginas de dados/legadas processadas; logs bronze preservam tentativas HTTP.",
    "complete": "HTTP 200, sem erro e sem truncamento.", "tls_verified": "Indica verificação TLS registrada na captura de origem.",
    "captured_at": "Instante da coleta na origem, em ISO 8601; não é data de transformação.",
    "error": "Condição de falha/truncamento preservada.", "bytes": "Bytes da captura; pode incluir respostas de erro.",
    "latency_ms": "Mediana das páginas legadas ou latência da última página HTTP no modo nativo.",
    "url": "URL pública do endpoint de origem.", "uf": "UF validada contra as 27 siglas; vazio se ausente/inválida.",
    "channel_type": "Agências, ATMs, Correspondentes, Digitais ou Telefônicos.",
    "city": "Município publicado.", "address": "Endereço publicado; sem geocodificação externa.",
    "postal_code": "CEP publicado como texto.", "code": "Código do ponto ou do serviço, conforme a tabela.",
    "currency": "Moeda informada; tarifas sem moeda usam BRL.", "service": "Nome do item de tarifa.",
    "brand": "Marca publicada pelo participante.", "product_type": "Tipo/modalidade da oferta.",
    "category": "Categoria publicada da operação de câmbio.", "audience": "Público-alvo informado na cotação.",
    "value": "Valor da cotação publicado, sem conversão cambial.", "updated_at": "Atualização informada pela instituição para a cotação.",
}


def dictionary():
    content = []
    for name, schema in SCHEMAS.items():
        content.append(f'<details class="schema" id="table-{name}"><summary><code>{name}</code><span>{len(schema)} campos · contrato Arrow</span></summary>')
        content.append(table(["Campo", "Tipo", "Semântica"], [(f.name, str(f.type), FIELD_HELP.get(f.name, "Campo conforme publicação.")) for f in schema]))
        content.append('</details>')
    return ''.join(content)


def source_excerpt(module, function):
    text = (HERE / module).read_text(encoding="utf-8")
    tree = ast.parse(text)
    target = next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function)
    return '\n'.join(text.splitlines()[target.lineno-1:target.end_lineno])


def code_examples():
    examples = [("storage.py", "atomic_write", "Escrita atômica e durável"),
                ("collect.py", "capture", "Paginação, preservação e limites"),
                ("normalize.py", "emit_product", "Unidades, tarifas e identidade de oferta"),
                ("build.py", "quality_checks", "Gates que controlam a publicação")]
    content = []
    for i, (module, function, title) in enumerate(examples):
        content.append(f'<details class="code-example"><summary>{escape(title)}<span>{module} · {function}()</span></summary><div class="codebar"><code>src/observatory/{module}</code><button class="copy" data-copy="code-{i}">Copiar</button></div><pre id="code-{i}"><code>{escape(source_excerpt(module,function))}</code></pre></details>')
    sql = (HERE / "sql" / "marts.sql").read_text(encoding="utf-8")
    content.append(f'<details class="code-example"><summary>SQL completo dos marts<span>sql/marts.sql · fonte única de métricas</span></summary><div class="codebar"><code>src/observatory/sql/marts.sql</code><button class="copy" data-copy="code-sql">Copiar</button></div><pre id="code-sql"><code>{escape(sql)}</code></pre></details>')
    return ''.join(content)


def generate(build_root: Path, destination: Path) -> Path:
    payload = read_json(build_root / "dashboard.json")
    result_path = build_root / "build.json"
    if not result_path.exists():
        result_path = build_root / "execution.json"
    result = read_json(result_path) if result_path.exists() else {}
    template = (HERE / "templates" / "manual.html").read_text(encoding="utf-8")
    gs = payload["group_metrics"]
    metrics = table(["Conglomerado", "Empresas", "Endpoints", "HTTP 200", "Ofertas", "Rede física", "Índice técnico"],
                    [(g["label"],g["companies"],g["endpoints"],g["http_ok"],number(g["products"]),number(g["physical_channels"]),g["quality_score"]) for g in gs])
    checks = table(["Controle", "Severidade", "Ocorrências", "Resultado"],
                   [(c["label"],c["severity"],c["failures"],"Aprovado" if c["passed"] else "Atenção") for c in payload["quality"]])
    build_tables = table(["Tabela gold", "Linhas"], [(k,number(v)) for k,v in result.get("tables",{}).items()])
    db = duckdb.connect(str(build_root / "warehouse.duckdb"), read_only=True)
    try:
        mart_schemas=[]
        for name in result.get("tables", {}):
            fields = db.execute(f'DESCRIBE "{name}"').fetchall()
            mart_schemas.append(f'<details class="schema"><summary><code>{name}</code><span>{number(result["tables"][name])} linhas</span></summary>' + table(["Coluna", "Tipo SQL"], [(r[0],r[1]) for r in fields]) + '</details>')
    finally:
        db.close()
    replacements = {
        "ORIGIN": "Replay de bronze importado" if payload["meta"]["origin"] == "imported_snapshot" else "Coleta direta das APIs públicas",
        "CAPTURE_DATE": payload["meta"]["captured_to"][:10],
        "VERSION": payload["meta"]["transform_version"], "SNAPSHOT": payload["meta"]["snapshot_id"],
        "BUILD": payload["meta"]["build_id"], "FINGERPRINT": payload["meta"]["source_fingerprint"],
        "CAPTURED_FROM": payload["meta"]["captured_from"], "CAPTURED_TO": payload["meta"]["captured_to"],
        "GENERATED": payload["meta"]["generated_at"], "ENDPOINTS": str(len(payload["endpoints"])),
        "MEGABYTES": f'{payload["meta"]["bronze_bytes"]/1e6:.1f}', "DURATION": str(result.get("duration_seconds", "—")),
        "METRICS": metrics, "CHECKS": checks, "TABLES": build_tables, "SCHEMAS": dictionary(),
        "MART_SCHEMAS": ''.join(mart_schemas), "CODE": code_examples(),
    }
    raw_keys = {"METRICS","CHECKS","TABLES","SCHEMAS","MART_SCHEMAS","CODE"}
    for key,value in replacements.items():
        template = template.replace(f"@@{key}@@", value if key in raw_keys else escape(value))
    atomic_write(destination, template.encode("utf-8"))
    return destination
