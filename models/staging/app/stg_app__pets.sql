select
    pet_id,
    member_id,
    clinic_id,
    trim(name)                               as pet_name_raw,
    {{ pet_name_core('name') }}              as pet_name_norm,
    lower(species)                           as species,
    cast(nullif(birth_date, '') as date)     as birth_date,
    {{ iso_to_utc('created_at') }}           as created_at_utc
from {{ source('raw_app', 'pets') }}
