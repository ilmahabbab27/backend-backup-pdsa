select *
from public.facilities
order by priority_score desc, current_load asc;

select *
from public.facilities
where facility_type = $1
order by priority_score desc, current_load asc;

insert into public.facilities (location_key, facility_type, capacity, current_load, priority_score, metadata)
values ($1, $2, $3, $4, $5, coalesce($6::jsonb, '{}'::jsonb))
on conflict (location_key)
do update set
  facility_type = excluded.facility_type,
  capacity = excluded.capacity,
  current_load = excluded.current_load,
  priority_score = excluded.priority_score,
  metadata = excluded.metadata;
