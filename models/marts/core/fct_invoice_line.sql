-- Every invoice line with a canonical service and whether the pet's wellness plan covered it on that date.
-- Plans with a yearly limit (e.g. 1 dental cleaning) only cover the first N uses per membership year.
with lines as (
    select * from {{ ref('stg_cornerstone__invoice_lines') }}
    union all
    select * from {{ ref('stg_allydvm__invoice_lines') }}
),
enriched as (
    select
        md5(l.invoice_line_source_key) as invoice_line_id, i.invoice_id, l.invoice_line_source_key, l.pims as source_pims,
        i.clinic_id, i.golden_patient_id, i.invoice_local_date, i.is_voided,
        l.item_code, l.item_description, l.quantity, l.unit_price_cents, l.discount_cents, l.line_net_cents,
        sc.canonical_service, sc.service_category,
        m.membership_id, m.plan_code, m.started_on as membership_started_on
    from lines l
    join {{ ref('int_invoices') }} i using (invoice_source_key)
    left join {{ ref('service_catalog') }} sc on sc.pims = l.pims and sc.item_code = l.item_code
    left join {{ ref('fct_membership') }} m
      on m.golden_patient_id = i.golden_patient_id
     and i.invoice_local_date >= m.started_on
     and i.invoice_local_date <= coalesce(m.cancelled_on, date '9999-12-31')
),
usage as (
    select e.*,
        pc.canonical_service is not null                                as service_in_plan,
        pc.annual_limit,
        case when e.membership_id is null then null
             else cast(floor((e.invoice_local_date - e.membership_started_on) / 365.0) as integer) end as membership_year,
        row_number() over (
            partition by e.membership_id, e.canonical_service,
                         cast(floor((e.invoice_local_date - e.membership_started_on) / 365.0) as integer), e.is_voided
            order by e.invoice_local_date, e.invoice_line_id)            as use_number_in_year
    from enriched e
    left join {{ ref('plan_coverage') }} pc on pc.plan_code = e.plan_code and pc.canonical_service = e.canonical_service
)
select
    invoice_line_id, invoice_id, invoice_line_source_key, source_pims, clinic_id, golden_patient_id, invoice_local_date,
    item_code, item_description, quantity, unit_price_cents, discount_cents, line_net_cents,
    canonical_service, service_category, canonical_service is null as is_unmapped_item,
    membership_id, plan_code, membership_year,
    (not is_voided and service_in_plan and (annual_limit is null or use_number_in_year <= annual_limit)) as is_plan_covered,
    (not is_voided and service_in_plan and annual_limit is not null and use_number_in_year > annual_limit) as is_over_plan_limit,
    is_voided
from usage
