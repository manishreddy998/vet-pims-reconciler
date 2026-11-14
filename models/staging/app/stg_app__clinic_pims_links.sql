select
    clinic_id,
    pims,
    practice_id,
    cast(active_from as date)                as active_from,
    cast(nullif(active_to, '') as date)      as active_to
from {{ source('raw_app', 'clinic_pims_links') }}
