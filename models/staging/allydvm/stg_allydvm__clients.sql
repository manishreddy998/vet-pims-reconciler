select
    'ad:' || practiceId || ':' || clientGuid                as client_source_key,
    practiceId                                              as practice_id,
    clientGuid                                              as pims_client_id,
    lower(trim(split_part(name, ',', 2)))                   as first_name_norm,   -- "Last, First"
    lower(trim(split_part(name, ',', 1)))                   as last_name_norm,
    {{ normalize_email('primaryEmail') }}                   as email_norm,
    {{ phone_digits('primaryPhone') }}                      as phone_digits
from {{ source('raw_allydvm', 'clients') }}
