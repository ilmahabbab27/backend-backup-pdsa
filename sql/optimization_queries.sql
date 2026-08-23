select *
from public.waste_points
where fill_level >= 80
order by fill_level desc;

select *
from public.waste_routes
where route_code = $1;

insert into public.waste_routes (
  route_code,
  start_location_key,
  end_location_key,
  total_distance_km,
  total_time_min,
  algorithm,
  path
)
values ($1, $2, $3, $4, $5, $6, coalesce($7::jsonb, '[]'::jsonb))
on conflict (route_code)
do update set
  start_location_key = excluded.start_location_key,
  end_location_key = excluded.end_location_key,
  total_distance_km = excluded.total_distance_km,
  total_time_min = excluded.total_time_min,
  algorithm = excluded.algorithm,
  path = excluded.path;
