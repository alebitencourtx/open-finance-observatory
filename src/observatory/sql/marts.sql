-- All business metrics live here; the dashboard only selects and formats them.
CREATE TABLE coverage AS
SELECT g.group_id, f.family_label,
       count(e.endpoint_id) AS endpoints,
       count(e.endpoint_id) FILTER (WHERE e.status = 200) AS http_ok,
       count(e.endpoint_id) FILTER (WHERE e.complete) AS complete,
       coalesce(sum(e.records), 0)::BIGINT AS records,
       bool_or(e.records > 0 AND e.status = 200) IS TRUE AS published,
       count(e.endpoint_id) > 0 AS declared
FROM dim_groups g CROSS JOIN dim_families f
LEFT JOIN endpoints e ON e.group_id = g.group_id AND e.family_label = f.family_label
GROUP BY ALL;

-- Reduce each offer to one observation before computing a market distribution.
-- These are distributions of published minimums, not volume-weighted customer rates.
CREATE TABLE rate_offers AS
SELECT group_id, company, cnpj, family_label, segment, product_id, name, product_type, indexer, unit,
       min(minimum) AS minimum, max(maximum) AS maximum, count(*) AS observations
FROM (SELECT r.*,p.product_type FROM rates r JOIN products p ON p.entity_id=r.product_id) WHERE valid
GROUP BY ALL;

CREATE TABLE rates_family AS
SELECT group_id, family_label, segment, product_type, indexer, unit, count(*) AS offers,
       round(min(minimum), 4) AS minimum,
       round(quantile_cont(minimum, 0.25), 4) AS p25,
       round(median(minimum), 4) AS median,
       round(quantile_cont(minimum, 0.75), 4) AS p75,
       round(max(maximum), 4) AS maximum
FROM rate_offers GROUP BY ALL;

CREATE TABLE channels_uf AS
SELECT group_id, uf, channel_type, count(*) AS count
FROM channels WHERE uf != '' GROUP BY ALL;

CREATE TABLE channels_type AS
SELECT group_id, channel_type, count(*) AS count
FROM channels GROUP BY ALL;

CREATE TABLE products_family AS
SELECT group_id, family_label, segment, count(*) AS count
FROM products GROUP BY ALL;

CREATE TABLE fees_family AS
SELECT group_id, family_label, segment, currency, code, service, count(*) AS count,
       count(*) FILTER (WHERE minimum = 0) AS zero_minimum,
       round(median(minimum), 2) AS median, round(max(maximum), 2) AS maximum
FROM fees WHERE valid GROUP BY ALL;

CREATE TABLE companies AS
WITH e AS (SELECT group_id, cnpj, any_value(company) AS company, count(*) AS endpoints,
                  count(*) FILTER (WHERE complete) AS complete, sum(records) AS records
           FROM endpoints GROUP BY group_id, cnpj),
     p AS (SELECT group_id, cnpj, count(*) AS products FROM products GROUP BY ALL),
     c AS (SELECT group_id, cnpj, count(*) AS channels FROM channels GROUP BY ALL)
SELECT e.*, coalesce(p.products,0) AS products, coalesce(c.channels,0) AS channels
FROM e LEFT JOIN p USING(group_id,cnpj) LEFT JOIN c USING(group_id,cnpj);

CREATE TABLE group_metrics AS
WITH ep AS (
    SELECT group_id, count(*) AS endpoints, count(DISTINCT cnpj) AS companies,
           count(*) FILTER (WHERE status=200) AS http_ok,
           count(*) FILTER (WHERE complete) AS complete,
           count(*) FILTER (WHERE status=200 AND records>0) AS with_data,
           count(*) FILTER (WHERE NOT tls_verified) AS insecure,
           count(*) FILTER (WHERE NOT complete) AS attention,
           sum(records) AS raw_records, sum(bytes) AS bytes,
           min(captured_at) AS captured_from, max(captured_at) AS captured_to
    FROM endpoints GROUP BY group_id
), pr AS (
    SELECT group_id, count(*) AS products,
           count(*) FILTER (WHERE family_label IN ('Cartões','Empréstimos','Financiamentos','Antecipação de recebíveis','Adiantamento a depositantes')) AS credit_products
    FROM products GROUP BY group_id
), rt AS (
    SELECT group_id, count(DISTINCT product_id) AS products_with_rate
    FROM rates WHERE valid AND family_label IN ('Cartões','Empréstimos','Financiamentos','Antecipação de recebíveis','Adiantamento a depositantes') GROUP BY group_id
), ch AS (
    SELECT group_id, count(*) AS channels,
           count(*) FILTER (WHERE channel_type IN ('Agências','ATMs','Correspondentes')) AS physical_channels,
           count(*) FILTER (WHERE channel_type IN ('Agências','ATMs','Correspondentes') AND uf!='') AS with_uf,
           count(*) FILTER (WHERE channel_type='Agências') AS branches,
           count(*) FILTER (WHERE channel_type='Correspondentes') AS agents,
           count(*) FILTER (WHERE channel_type='ATMs') AS atms,
           count(DISTINCT nullif(uf,'')) AS ufs
    FROM channels GROUP BY group_id
), cv AS (
    SELECT group_id, count(*) FILTER (WHERE declared) AS declared_families,
           count(*) FILTER (WHERE published) AS published_families FROM coverage GROUP BY group_id
), components AS (
    SELECT g.*, ep.* EXCLUDE(group_id),
           coalesce(pr.products,0) AS products, coalesce(pr.credit_products,0) AS credit_products,
           coalesce(ch.channels,0) AS channels, coalesce(ch.physical_channels,0) AS physical_channels,
           coalesce(ch.branches,0) AS branches, coalesce(ch.agents,0) AS agents, coalesce(ch.atms,0) AS atms,
           coalesce(ch.ufs,0) AS ufs, cv.declared_families, cv.published_families,
           round(100.0*cv.published_families/14,2) AS coverage_scope,
           round(100.0*cv.published_families/nullif(cv.declared_families,0),2) AS coverage_declared,
           round(100.0*ep.complete/nullif(ep.endpoints,0),2) AS collection_score,
           round(100.0*ep.with_data/nullif(ep.http_ok,0),2) AS data_score,
           round(100.0*ch.with_uf/nullif(ch.physical_channels,0),2) AS geography_score,
           round(100.0*coalesce(rt.products_with_rate,0)/nullif(pr.credit_products,0),2) AS rate_score
    FROM dim_groups g JOIN ep USING(group_id)
    LEFT JOIN pr USING(group_id) LEFT JOIN ch USING(group_id) LEFT JOIN rt USING(group_id) JOIN cv USING(group_id)
)
SELECT *, round(list_avg([collection_score, data_score, geography_score, rate_score]),1) AS quality_score
FROM components;

CREATE TABLE product_catalog AS
SELECT p.*, r.minimum AS rate_minimum, r.maximum AS rate_maximum,
       e.url AS source_url
FROM products p LEFT JOIN (
    SELECT product_id, min(minimum) AS minimum, max(maximum) AS maximum
    FROM rates WHERE valid AND unit='pct_month' GROUP BY product_id
) r ON p.entity_id=r.product_id
JOIN endpoints e ON p.endpoint_id=e.endpoint_id;
