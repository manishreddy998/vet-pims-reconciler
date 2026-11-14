select
    payment_id,
    membership_id,
    {{ iso_to_utc('charged_at') }}           as charged_at_utc,
    cast(amount_cents as bigint)             as amount_cents,
    status
from {{ source('raw_app', 'payments') }}
