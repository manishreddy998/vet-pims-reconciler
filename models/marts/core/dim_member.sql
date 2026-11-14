select member_id, first_name, last_name, email_norm as email, phone_digits as phone, created_at_utc
from {{ ref('stg_app__members') }}
