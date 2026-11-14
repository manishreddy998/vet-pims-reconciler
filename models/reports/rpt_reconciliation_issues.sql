-- Everything the pipeline had to decide or could not resolve, one row per issue, ready for an ops queue.
with issues as (
    select 'plan_pet_not_found_in_pims' as issue_type, 'high' as severity, d.clinic_id, 'pet' as entity_type, d.app_pet_id as entity_key,
           'Pet "' || d.pet_name || '" is enrolled in a plan but has no patient record at its clinic' as detail
    from {{ ref('dim_patient') }} d where d.is_plan_pet and d.n_pims_records = 0
    union all
    select 'plan_pet_registered_at_other_clinic', 'high', d.clinic_id, 'pet', d.app_pet_id,
           'Matched by owner contact and pet name, but the PIMS record is at a different clinic than the app says'
    from {{ ref('dim_patient') }} d where d.clinic_mismatch
    union all
    select 'low_confidence_match', 'medium', d.clinic_id, 'pet', d.app_pet_id,
           'Matched with rule ' || d.match_rule || ' at confidence ' || cast(d.match_confidence as varchar)
    from {{ ref('dim_patient') }} d where d.match_confidence < 0.95 and not d.clinic_mismatch
    union all
    select 'active_membership_for_deceased_pet', 'high', m.clinic_id, 'membership', m.membership_id,
           'PIMS marks the pet deceased but the membership is still active and billing'
    from {{ ref('fct_membership') }} m where m.is_active_for_deceased_pet
    union all
    select 'orphaned_booking_after_pims_migration', 'low', a.clinic_id, 'appointment', a.appointment_source_key,
           'Booked in the old PIMS for a date after the clinic switched systems. Excluded from appointment counts'
    from {{ ref('int_appointments') }} a where a.excluded_reason = 'orphaned_after_pims_migration'
    union all
    select 'superseded_imported_history', 'info', a.clinic_id, 'appointment', a.appointment_source_key,
           'History the new PIMS imported from the old one. The old system stays the record of truth for those dates'
    from {{ ref('int_appointments') }} a where a.excluded_reason = 'superseded_imported_history'
    union all
    select 'unresolved_past_booking', 'medium', a.clinic_id, 'appointment', a.appointment_source_key,
           'Still "' || a.raw_status || '" more than {{ var("stale_booking_hours") }}h after its start time'
    from {{ ref('int_appointments') }} a where a.is_record_of_truth and a.resolved_status = 'unresolved'
    union all
    select 'invoice_math_mismatch', 'medium', i.clinic_id, 'invoice', i.invoice_source_key,
           'Reported total is off from lines + tax by ' || cast(i.math_gap_cents as varchar) || ' cents'
    from {{ ref('int_invoices') }} i where i.has_math_mismatch and not i.is_voided
    union all
    select 'unmapped_item_code', 'medium', min(l.clinic_id), 'item_code', l.source_pims || ':' || l.item_code,
           cast(count(*) as varchar) || ' invoice lines use code ' || l.item_code || ' ("' || min(l.item_description) || '"), which is not in the service catalog'
    from {{ ref('fct_invoice_line') }} l where l.is_unmapped_item group by l.source_pims, l.item_code
    union all
    select 'completed_visit_without_invoice', 'low', a.clinic_id, 'appointment', a.appointment_source_key,
           'Completed visit with no invoice on the same day'
    from {{ ref('fct_appointment') }} a where a.is_visit and a.invoice_id is null
    union all
    select 'stale_feed', 'high', f.clinic_id, 'practice', f.practice_id,
           f.pims || ' feed for ' || f.clinic_name || ' last updated ' || cast(f.hours_since_last_update as varchar) || ' hours ago'
    from {{ ref('rpt_feed_freshness') }} f where f.is_stale
)
select md5(issue_type || ':' || entity_key) as issue_id, i.*, c.clinic_name
from issues i
left join {{ ref('dim_clinic') }} c using (clinic_id)
