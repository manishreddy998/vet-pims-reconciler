-- One row per PIMS practice feed, with the clinic it belongs to and the dates it is the system of record.
select
    l.practice_id,
    l.pims,
    l.clinic_id,
    c.clinic_name,
    c.clinic_timezone,
    c.sales_tax_rate,
    l.active_from,
    l.active_to,
    l.active_to is null as is_current_feed
from {{ ref('stg_app__clinic_pims_links') }} l
join {{ ref('stg_app__clinics') }} c using (clinic_id)
