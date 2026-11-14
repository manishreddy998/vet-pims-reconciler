select
    'cs:' || PRACTICE_ID || ':' || PATIENT_ID     as patient_source_key,
    'cs:' || PRACTICE_ID || ':' || CLIENT_ID      as client_source_key,
    PRACTICE_ID                                   as practice_id,
    PATIENT_ID                                    as pims_patient_id,
    trim(PATIENT_NAME)                            as pet_name_raw,
    {{ pet_name_core('PATIENT_NAME') }}           as pet_name_norm,
    case upper(SPECIES) when 'CANINE' then 'dog' when 'FELINE' then 'cat' else 'other' end as species,
    BREED                                         as breed,
    {{ parse_us_date('BIRTH_DATE') }}             as birth_date,
    DECEASED = 'Y'                                as is_deceased,
    {{ parse_us_date('DECEASED_DATE') }}          as deceased_on
from {{ source('raw_cornerstone', 'patients') }}
