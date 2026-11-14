select
    membership_id,
    pet_id,
    plan_code,
    cast(started_at as date)                       as started_on,
    cast(nullif(cancelled_at, '') as date)         as cancelled_on,
    cast(monthly_price_cents as bigint)            as monthly_price_cents
from {{ source('raw_app', 'memberships') }}
