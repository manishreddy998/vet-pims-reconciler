-- Invoices on one money definition: net (before tax), tax, gross. The two PIMS report totals differently.
with cs_lines as (
    select invoice_source_key, sum(line_net_cents) as lines_net_cents, count(*) as n_lines
    from {{ ref('stg_cornerstone__invoice_lines') }} group by 1
),
ad_lines as (
    select invoice_source_key, sum(line_net_cents) as lines_net_cents, count(*) as n_lines
    from {{ ref('stg_allydvm__invoice_lines') }} group by 1
),
cs as (
    select i.invoice_source_key, 'cornerstone' as pims, i.practice_id, i.patient_source_key, i.client_source_key,
           i.invoice_local_date, i.is_voided, l.n_lines,
           l.lines_net_cents                                               as net_cents,
           i.reported_total_cents - l.lines_net_cents                      as tax_cents,
           i.reported_total_cents                                          as gross_cents,
           -- Cornerstone total includes tax: compare it with lines + expected tax
           i.reported_total_cents - (l.lines_net_cents + cast(round(l.lines_net_cents * pr.sales_tax_rate) as bigint)) as math_gap_cents
    from {{ ref('stg_cornerstone__invoices') }} i
    join {{ ref('int_practices') }} pr using (practice_id)
    left join cs_lines l using (invoice_source_key)
),
ad as (
    select i.invoice_source_key, 'allydvm', i.practice_id, i.patient_source_key, i.client_source_key,
           cast({{ utc_to_local('i.posted_at_utc', 'pr.clinic_timezone') }} as date), i.is_voided, l.n_lines,
           l.lines_net_cents,
           i.reported_tax_cents,
           l.lines_net_cents + i.reported_tax_cents,
           -- AllyDVM total excludes tax: it should equal the sum of the lines
           i.reported_total_cents - l.lines_net_cents
    from {{ ref('stg_allydvm__invoices') }} i
    join {{ ref('int_practices') }} pr using (practice_id)
    left join ad_lines l using (invoice_source_key)
)
select
    md5(u.invoice_source_key) as invoice_id, u.*, pr.clinic_id, x.golden_patient_id,
    abs(u.math_gap_cents) > {{ var('invoice_tolerance_cents') }} as has_math_mismatch
from (select * from cs union all select * from ad) u
join {{ ref('int_practices') }} pr using (practice_id)
left join {{ ref('int_patient_xref') }} x using (patient_source_key)
