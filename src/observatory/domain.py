"""Versioned analytical contracts. Null is absence; zero remains zero."""
import pyarrow as pa

FAMILIES = {
    "accounts": "Contas", "creditcards": "Cartões", "loans": "Empréstimos",
    "financings": "Financiamentos", "invoicefinancings": "Antecipação de recebíveis",
    "unarranged": "Adiantamento a depositantes", "investments": "Investimentos", "exchange": "Câmbio",
    "insurance": "Seguros", "pension": "Previdência", "capitalization": "Capitalização",
    "acquiring": "Adquirência", "acquiring-services": "Adquirência", "channels": "Canais", "admin": "Métricas",
}
FAMILY_ORDER = list(dict.fromkeys(FAMILIES.values()))
CREDIT = ["Cartões", "Empréstimos", "Financiamentos", "Antecipação de recebíveis", "Adiantamento a depositantes"]
UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())


def family_label(family):
    return FAMILIES.get(family.removeprefix("opendata-").split("_")[0], "Fora do escopo")


def segment(family):
    return "PF" if "personal" in family else "PJ" if "business" in family else "NA"


TEXT = pa.string()
INT = pa.int64()
FLOAT = pa.float64()
BOOL = pa.bool_()
BASE = [(k, TEXT) for k in ("group_id", "company", "cnpj", "family", "family_label", "segment", "endpoint_id", "source_sha")]
SCHEMAS = {
    "endpoints": pa.schema(BASE + [("url", TEXT), ("captured_at", TEXT), ("status", INT), ("records", INT),
                                  ("pages", INT), ("complete", BOOL), ("tls_verified", BOOL), ("error", TEXT),
                                  ("bytes", INT), ("latency_ms", FLOAT)]),
    "products": pa.schema(BASE + [("entity_id", TEXT), ("name", TEXT), ("product_type", TEXT), ("brand", TEXT)]),
    "rates": pa.schema(BASE + [("entity_id", TEXT), ("product_id", TEXT), ("name", TEXT), ("indexer", TEXT),
                              ("unit", TEXT), ("minimum", FLOAT), ("maximum", FLOAT), ("raw_minimum", TEXT),
                              ("raw_maximum", TEXT), ("effective_minimum", FLOAT), ("effective_maximum", FLOAT),
                              ("valid", BOOL), ("reason", TEXT), ("json_path", TEXT)]),
    "fees": pa.schema(BASE + [("entity_id", TEXT), ("product_id", TEXT), ("name", TEXT), ("service", TEXT),
                             ("code", TEXT), ("currency", TEXT), ("minimum", FLOAT), ("maximum", FLOAT), ("valid", BOOL), ("reason", TEXT), ("json_path", TEXT)]),
    "channels": pa.schema(BASE + [("entity_id", TEXT), ("channel_type", TEXT), ("name", TEXT), ("code", TEXT),
                                 ("uf", TEXT), ("city", TEXT), ("address", TEXT), ("postal_code", TEXT)]),
    "exchange": pa.schema(BASE + [("entity_id", TEXT), ("currency", TEXT), ("category", TEXT), ("audience", TEXT),
                                 ("value", FLOAT), ("updated_at", TEXT), ("transaction_type", TEXT), ("delivery", TEXT),
                                 ("range_category", TEXT), ("vet_minimum", FLOAT), ("vet_maximum", FLOAT), ("vet_prices", TEXT)]),
    "quarantine": pa.schema(BASE + [("json_path", TEXT), ("reason", TEXT), ("raw_json", TEXT)]),
}
