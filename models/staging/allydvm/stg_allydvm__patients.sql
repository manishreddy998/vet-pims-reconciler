select
    'ad:' || practiceId || ':' || patientGuid               as patient_source_key,
    'ad:' || practiceId || ':' || clientGuid                as client_source_key,
    practiceId                                              as practice_id,
    patientGuid                                             as pims_patient_id,
    trim(name)                                              as pet_name_raw,
    {{ pet_name_core('name') }}                             as pet_name_norm,
    case lower(species) when 'dog' then 'dog' when 'cat' then 'cat' else 'other' end as species,
    breed,
    cast(nullif(dateOfBirth, '') as date)                   as birth_date,
    deceasedAt is not null                                  as is_deceased,
    cast(nullif(deceasedAt, '') as date)                    as deceased_on
from {{ source('raw_allydvm', 'patients') }}
