select
    'cs:' || PRACTICE_ID || ':' || INVOICE_NO                     as invoice_source_key,
    'cs:' || PRACTICE_ID || ':' || INVOICE_NO || ':' || LINE_NO    as invoice_line_source_key,
    'cornerstone'                                                 as pims,
    cast(LINE_NO as integer)                                      as line_number,
    ITEM_CODE                                                     as item_code,
    DESCRIPTION                                                   as item_description,
    cast(QTY as integer)                                          as quantity,
    {{ money_to_cents('UNIT_PRICE') }}                            as unit_price_cents,
    {{ money_to_cents('DISCOUNT') }}                              as discount_cents,
    {{ money_to_cents('EXTENDED') }}                              as line_net_cents
from {{ source('raw_cornerstone', 'invoice_items') }}
