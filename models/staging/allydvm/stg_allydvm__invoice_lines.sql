select
    'ad:' || practiceId || ':' || invoiceGuid                              as invoice_source_key,
    'ad:' || practiceId || ':' || invoiceGuid || ':' || lineNumber         as invoice_line_source_key,
    'allydvm'                                                              as pims,
    cast(lineNumber as integer)                                            as line_number,
    sku                                                                    as item_code,
    description                                                            as item_description,
    cast(quantity as integer)                                              as quantity,
    cast(unitPriceCents as bigint)                                         as unit_price_cents,
    cast(discountCents as bigint)                                          as discount_cents,
    cast(quantity as integer) * cast(unitPriceCents as bigint) - cast(discountCents as bigint) as line_net_cents
from {{ source('raw_allydvm', 'invoice_lines') }}
