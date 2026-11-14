select appointment_id from {{ ref('fct_appointment') }} where is_visit and local_date > current_date
