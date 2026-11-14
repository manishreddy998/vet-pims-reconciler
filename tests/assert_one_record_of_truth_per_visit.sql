-- The same animal cannot have two counted visits at the same clinic within 30 minutes.
-- This is what double counting looks like when a clinic changes PIMS.
select a.appointment_id, b.appointment_id as other_appointment_id
from {{ ref('fct_appointment') }} a
join {{ ref('fct_appointment') }} b
  on a.golden_patient_id = b.golden_patient_id and a.clinic_id = b.clinic_id
 and a.appointment_id < b.appointment_id and a.is_visit and b.is_visit
 and abs(extract(epoch from (a.start_utc - b.start_utc))) < 1800
