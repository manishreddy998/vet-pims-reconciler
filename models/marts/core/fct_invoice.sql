select
    invoice_id, invoice_source_key, pims as source_pims, clinic_id, golden_patient_id, invoice_local_date,
    n_lines, net_cents, tax_cents, gross_cents, math_gap_cents, has_math_mismatch, is_voided
from {{ ref('int_invoices') }}
