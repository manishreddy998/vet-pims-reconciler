-- ONE definition of an appointment: a booking for a patient at a clinic, taken from the PIMS that was the
-- clinic's system of record on that date. A "visit" is an appointment whose resolved status is completed.
with appts as (
    select * from {{ ref('int_appointments') }} where is_record_of_truth
),
inv as (
    select golden_patient_id, clinic_id, invoice_local_date, min(invoice_id) as invoice_id
    from {{ ref('int_invoices') }} where not is_voided group by 1, 2, 3
)
select
    a.appointment_id, a.golden_patient_id, a.clinic_id, a.pims as source_pims, a.appointment_source_key,
    a.start_utc, a.start_local, a.local_date, a.appointment_type, a.duration_minutes,
    a.raw_status, a.resolved_status as status,
    a.resolved_status = 'completed'                                      as is_visit,
    d.is_plan_pet,
    i.invoice_id,
    a.n_versions                                                         as n_source_versions,
    a.source_updated_at_utc
from appts a
left join {{ ref('dim_patient') }} d using (golden_patient_id)
left join inv i
  on a.resolved_status = 'completed' and i.golden_patient_id = a.golden_patient_id
 and i.clinic_id = a.clinic_id and i.invoice_local_date = a.local_date
