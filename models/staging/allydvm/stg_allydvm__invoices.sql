select
    'ad:' || practiceId || ':' || invoiceGuid          as invoice_source_key,
    'ad:' || practiceId || ':' || clientGuid           as client_source_key,
    'ad:' || practiceId || ':' || patientGuid          as patient_source_key,
    practiceId                                         as practice_id,
    invoiceGuid                                        as pims_invoice_id,
    {{ iso_to_utc('postedAt') }}                       as posted_at_utc,
    cast(totalCents as bigint)                         as reported_total_cents,  -- AllyDVM totals EXCLUDE tax
    cast(taxCents as bigint)                           as reported_tax_cents,
    state = 'voided'                                   as is_voided
from {{ source('raw_allydvm', 'invoices') }}
