select
    clinic_id,
    name                                     as clinic_name,
    timezone                                 as clinic_timezone,
    cast(sales_tax_rate as decimal(6, 4))    as sales_tax_rate,
    cast(onboarded_at as date)               as onboarded_on
from {{ source('raw_app', 'clinics') }}
