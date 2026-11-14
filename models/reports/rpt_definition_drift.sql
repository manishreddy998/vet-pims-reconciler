-- "How many visits did we have that month?" answered the ways people actually answer it. Only the last column is right.
with raw_rows as (   -- 1. count every row in every export file
    select cast(date_trunc('month', {{ parse_us_date('APPT_DATE') }}) as date) as month_start, count(*) as n
    from {{ source('raw_cornerstone', 'appointments') }} group by 1
    union all
    select cast(date_trunc('month', {{ iso_to_utc('startAt') }}) as date), count(*)
    from {{ source('raw_allydvm', 'appointments') }} group by 1
),
any_status as (   -- 2. dedupe versions, but count every appointment in both systems (cancelled, no-shows, stale bookings too)
    select cast(date_trunc('month', start_local) as date) as month_start, count(*) as n
    from {{ ref('int_appointments') }} group by 1
),
completed_both as (   -- 3. only completed, but add up both systems (double counts a clinic during its PIMS switch)
    select cast(date_trunc('month', start_local) as date) as month_start, count(*) as n
    from {{ ref('int_appointments') }} where canonical_status = 'completed' group by 1
),
canonical as (   -- 4. one system of record per clinic per date, latest version, clinic-local date
    select cast(date_trunc('month', local_date) as date) as month_start, count(*) as n
    from {{ ref('fct_appointment') }} where is_visit group by 1
)
select
    c.month_start,
    (select sum(n) from raw_rows r where r.month_start = c.month_start)        as naive_export_rows,
    (select sum(n) from any_status r where r.month_start = c.month_start)      as naive_any_status,
    (select sum(n) from completed_both r where r.month_start = c.month_start)  as naive_completed_both_systems,
    c.n                                                                        as canonical_visits
from canonical c
where c.month_start < cast(date_trunc('month', current_date) as date)
