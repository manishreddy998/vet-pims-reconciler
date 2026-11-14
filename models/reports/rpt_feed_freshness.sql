-- When did each practice feed last send us something? A clinic whose feed stopped looks like a clinic with no visits.
with last_seen as (
    select practice_id, max(source_updated_at_utc) as last_source_update_utc
    from {{ ref('int_appointments') }} group by 1
)
select
    p.practice_id, p.pims, p.clinic_id, p.clinic_name, p.is_current_feed, l.last_source_update_utc,
    round(extract(epoch from (({{ dbt.current_timestamp() }} at time zone 'UTC') - l.last_source_update_utc)) / 3600.0, 1) as hours_since_last_update,
    p.is_current_feed
      and extract(epoch from (({{ dbt.current_timestamp() }} at time zone 'UTC') - l.last_source_update_utc)) / 3600.0 > {{ var('feed_stale_hours') }} as is_stale
from {{ ref('int_practices') }} p
left join last_seen l using (practice_id)
