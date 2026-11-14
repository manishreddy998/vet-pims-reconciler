select
    'cs:' || PRACTICE_ID || ':' || INVOICE_NO     as invoice_source_key,
    'cs:' || PRACTICE_ID || ':' || CLIENT_ID      as client_source_key,
    'cs:' || PRACTICE_ID || ':' || PATIENT_ID     as patient_source_key,
    PRACTICE_ID                                   as practice_id,
    INVOICE_NO                                    as pims_invoice_id,
    {{ parse_us_date('INVOICE_DATE') }}           as invoice_local_date,
    {{ money_to_cents('TOTAL') }}                 as reported_total_cents,  -- Cornerstone totals INCLUDE tax
    STATUS = 'V'                                  as is_voided
from {{ source('raw_cornerstone', 'invoices') }}
