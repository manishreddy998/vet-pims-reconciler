{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

{% test no_stale_feeds(model) %}
select * from {{ model }} where is_stale
{% endtest %}
