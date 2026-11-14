select
    'cs:' || PRACTICE_ID || ':' || CLIENT_ID      as client_source_key,
    PRACTICE_ID                                   as practice_id,
    CLIENT_ID                                     as pims_client_id,
    lower(trim(FIRST_NAME))                       as first_name_norm,
    lower(trim(LAST_NAME))                        as last_name_norm,
    {{ normalize_email('EMAIL') }}                as email_norm,
    {{ phone_digits('PHONE') }}                   as phone_digits
from {{ source('raw_cornerstone', 'clients') }}
