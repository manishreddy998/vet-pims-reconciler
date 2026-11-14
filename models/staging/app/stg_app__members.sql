select
    member_id,
    trim(first_name)                         as first_name,
    trim(last_name)                          as last_name,
    lower(trim(split_part(last_name, '-', 1))) as last_name_norm,
    {{ normalize_email('email') }}           as email_norm,
    {{ phone_digits('phone') }}              as phone_digits,
    {{ iso_to_utc('created_at') }}           as created_at_utc
from {{ source('raw_app', 'members') }}
