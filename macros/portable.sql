{# Small cross-database helpers. The project runs on DuckDB locally and on Postgres in production. #}

{% macro parse_us_date(col) %}{{ return(adapter.dispatch('parse_us_date')(col)) }}{% endmacro %}
{% macro default__parse_us_date(col) %}to_date(nullif(trim({{ col }}), ''), 'MM/DD/YYYY'){% endmacro %}
{% macro duckdb__parse_us_date(col) %}cast(strptime(nullif(trim({{ col }}), ''), '%m/%d/%Y') as date){% endmacro %}

{% macro parse_us_timestamp(date_col, time_col) %}{{ return(adapter.dispatch('parse_us_timestamp')(date_col, time_col)) }}{% endmacro %}
{% macro default__parse_us_timestamp(date_col, time_col) %}to_timestamp({{ date_col }} || ' ' || {{ time_col }}, 'MM/DD/YYYY HH12:MI AM')::timestamp{% endmacro %}
{% macro duckdb__parse_us_timestamp(date_col, time_col) %}strptime({{ date_col }} || ' ' || {{ time_col }}, '%m/%d/%Y %I:%M %p'){% endmacro %}

{% macro edit_distance(a, b) %}{{ return(adapter.dispatch('edit_distance')(a, b)) }}{% endmacro %}
{# Postgres needs the fuzzystrmatch extension: create extension if not exists fuzzystrmatch; #}
{% macro default__edit_distance(a, b) %}levenshtein({{ a }}, {{ b }}){% endmacro %}

{# ISO-8601 text with offset or Z -> naive UTC timestamp #}
{% macro iso_to_utc(col) %}(cast({{ col }} as timestamptz) at time zone 'UTC'){% endmacro %}

{# naive local wall-clock time in a clinic's time zone -> naive UTC timestamp #}
{% macro local_to_utc(ts, tz) %}(({{ ts }}) at time zone {{ tz }}) at time zone 'UTC'{% endmacro %}

{# naive UTC timestamp -> naive local wall-clock time in the clinic's time zone #}
{% macro utc_to_local(ts, tz) %}(({{ ts }}) at time zone 'UTC') at time zone {{ tz }}{% endmacro %}

{% macro money_to_cents(col) %}cast(round(cast(nullif(replace(replace(trim({{ col }}), '$', ''), ',', ''), '') as decimal(14, 2)) * 100) as bigint){% endmacro %}

{# lower-case, trimmed, with plus-addressing removed: Jane+vet@x.com -> jane@x.com #}
{% macro normalize_email(col) %}nullif(regexp_replace(lower(trim({{ col }})), '\+[^@]*@', '@'), ''){% endmacro %}

{# last 10 digits of any phone format #}
{% macro phone_digits(col) %}nullif(right(regexp_replace(coalesce({{ col }}, ''), '[^0-9]', '', 'g'), 10), ''){% endmacro %}

{% macro pet_name_core(col) %}nullif(trim(regexp_replace(lower(trim({{ col }})), '[^a-z ]', '', 'g')), ''){% endmacro %}
