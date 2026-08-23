select * from public.locations order by name;

select from_location_key, to_location_key, distance_km, travel_time_min, is_bidirectional
from public.roads;

select *
from public.roads
where from_location_key = $1
  and to_location_key = $2;

insert into public.roads (from_location_key, to_location_key, distance_km, travel_time_min, is_bidirectional, metadata)
values ($1, $2, $3, $4, $5, coalesce($6::jsonb, '{}'::jsonb))
on conflict (from_location_key, to_location_key)
do update set
  distance_km = excluded.distance_km,
  travel_time_min = excluded.travel_time_min,
  is_bidirectional = excluded.is_bidirectional,
  metadata = excluded.metadata;
