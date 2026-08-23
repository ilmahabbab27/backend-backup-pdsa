select *
from public.emergency_vehicles
where status = 'available'
order by vehicle_code;

select *
from public.resource_requests
where status = 'open'
order by
  case priority
    when 'critical' then 1
    when 'high' then 2
    when 'medium' then 3
    else 4
  end,
  created_at asc;

update public.resource_requests
set assigned_vehicle_id = $1,
    status = 'assigned',
    updated_at = now()
where request_code = $2;

update public.emergency_vehicles
set status = $1,
    current_location_key = $2
where vehicle_code = $3;
