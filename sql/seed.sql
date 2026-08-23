insert into public.locations (location_key, name, type, latitude, longitude, metadata) values
('city-hall', 'City Hall', 'administrative', 6.9271, 79.8612, '{}'::jsonb),
('central-hospital', 'Central Hospital', 'hospital', 6.9282, 79.8631, '{}'::jsonb),
('community-hospital', 'Community Hospital', 'hospital', 6.9249, 79.8579, '{}'::jsonb),
('police-station', 'Police Station', 'emergency', 6.9310, 79.8645, '{}'::jsonb),
('fire-station', 'Fire Station', 'emergency', 6.9231, 79.8604, '{}'::jsonb),
('university', 'University', 'education', 6.9295, 79.8662, '{}'::jsonb),
('bus-station', 'Bus Station', 'transport', 6.9257, 79.8626, '{}'::jsonb),
('shopping-center', 'Shopping Center', 'commercial', 6.9279, 79.8681, '{}'::jsonb),
('waste-center', 'Waste Center', 'utility', 6.9218, 79.8588, '{}'::jsonb),
('residential', 'Residential Zone', 'residential', 6.9262, 79.8569, '{}'::jsonb),
('public-park', 'Public Park', 'recreation', 6.9306, 79.8599, '{}'::jsonb)
on conflict (location_key) do update set
  name = excluded.name,
  type = excluded.type,
  latitude = excluded.latitude,
  longitude = excluded.longitude,
  metadata = excluded.metadata;

insert into public.roads (from_location_key, to_location_key, distance_km, travel_time_min, is_bidirectional, metadata) values
('city-hall', 'bus-station', 1.20, 4.0, true, '{}'::jsonb),
('bus-station', 'central-hospital', 2.80, 8.0, true, '{}'::jsonb),
('city-hall', 'police-station', 1.00, 3.0, true, '{}'::jsonb),
('police-station', 'fire-station', 1.50, 5.0, true, '{}'::jsonb),
('fire-station', 'community-hospital', 2.20, 7.0, true, '{}'::jsonb),
('community-hospital', 'residential', 1.40, 4.0, true, '{}'::jsonb),
('residential', 'waste-center', 3.30, 10.0, true, '{}'::jsonb),
('shopping-center', 'public-park', 1.70, 5.0, true, '{}'::jsonb)
on conflict (from_location_key, to_location_key) do update set
  distance_km = excluded.distance_km,
  travel_time_min = excluded.travel_time_min,
  is_bidirectional = excluded.is_bidirectional,
  metadata = excluded.metadata;

insert into public.facilities (location_key, facility_type, capacity, current_load, priority_score, metadata) values
('central-hospital', 'hospital', 300, 180, 0.9400, '{}'::jsonb),
('community-hospital', 'hospital', 180, 95, 0.8600, '{}'::jsonb),
('police-station', 'police', 50, 22, 0.9100, '{}'::jsonb),
('fire-station', 'fire', 40, 15, 0.9200, '{}'::jsonb),
('public-park', 'recreation', 500, 120, 0.6200, '{}'::jsonb)
on conflict (location_key) do update set
  facility_type = excluded.facility_type,
  capacity = excluded.capacity,
  current_load = excluded.current_load,
  priority_score = excluded.priority_score,
  metadata = excluded.metadata;

insert into public.emergency_vehicles (vehicle_code, vehicle_type, status, current_location_key, metadata) values
('AMB-01', 'ambulance', 'available', 'central-hospital', '{}'::jsonb),
('AMB-02', 'ambulance', 'busy', 'community-hospital', '{}'::jsonb),
('FIR-01', 'fire-truck', 'available', 'fire-station', '{}'::jsonb),
('POL-01', 'police-car', 'available', 'police-station', '{}'::jsonb)
on conflict (vehicle_code) do update set
  vehicle_type = excluded.vehicle_type,
  status = excluded.status,
  current_location_key = excluded.current_location_key,
  metadata = excluded.metadata;

insert into public.resource_requests (request_code, requester_name, priority, incident_location_key, status, metadata) values
('REQ-001', 'City Clinic', 'critical', 'residential', 'open', '{}'::jsonb),
('REQ-002', 'Main Market', 'high', 'shopping-center', 'open', '{}'::jsonb)
on conflict (request_code) do update set
  requester_name = excluded.requester_name,
  priority = excluded.priority,
  incident_location_key = excluded.incident_location_key,
  status = excluded.status,
  metadata = excluded.metadata;

insert into public.waste_points (location_key, bin_count, fill_level, service_area, metadata) values
('residential', 12, 86.50, 'north', '{}'::jsonb),
('shopping-center', 8, 72.00, 'central', '{}'::jsonb),
('public-park', 6, 90.25, 'west', '{}'::jsonb)
on conflict (location_key) do update set
  bin_count = excluded.bin_count,
  fill_level = excluded.fill_level,
  service_area = excluded.service_area,
  metadata = excluded.metadata;

insert into public.network_metrics (location_key, degree_centrality, betweenness_centrality, closeness_centrality, pagerank, metadata) values
('city-hall', 0.6500, 0.3200, 0.7100, 0.082500, '{}'::jsonb),
('central-hospital', 0.7200, 0.4800, 0.7600, 0.094200, '{}'::jsonb),
('bus-station', 0.6800, 0.4100, 0.7400, 0.088800, '{}'::jsonb)
on conflict (location_key) do update set
  degree_centrality = excluded.degree_centrality,
  betweenness_centrality = excluded.betweenness_centrality,
  closeness_centrality = excluded.closeness_centrality,
  pagerank = excluded.pagerank,
  metadata = excluded.metadata;
