create extension if not exists "pgcrypto";

create table if not exists public.locations (
  id uuid primary key default gen_random_uuid(),
  location_key text unique not null,
  name text not null,
  type text not null,
  latitude double precision,
  longitude double precision,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.roads (
  id uuid primary key default gen_random_uuid(),
  from_location_key text not null references public.locations(location_key) on delete cascade,
  to_location_key text not null references public.locations(location_key) on delete cascade,
  distance_km numeric(10,2) not null,
  travel_time_min numeric(10,2),
  is_bidirectional boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (from_location_key, to_location_key)
);

create table if not exists public.facilities (
  id uuid primary key default gen_random_uuid(),
  location_key text not null unique references public.locations(location_key) on delete cascade,
  facility_type text not null,
  capacity integer,
  current_load integer not null default 0,
  priority_score numeric(10,4) not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.emergency_vehicles (
  id uuid primary key default gen_random_uuid(),
  vehicle_code text unique not null,
  vehicle_type text not null,
  status text not null default 'available',
  current_location_key text references public.locations(location_key) on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.resource_requests (
  id uuid primary key default gen_random_uuid(),
  request_code text unique not null,
  requester_name text,
  priority text not null,
  incident_location_key text references public.locations(location_key) on delete set null,
  status text not null default 'open',
  assigned_vehicle_id uuid references public.emergency_vehicles(id) on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.waste_points (
  id uuid primary key default gen_random_uuid(),
  location_key text not null unique references public.locations(location_key) on delete cascade,
  bin_count integer not null default 0,
  fill_level numeric(5,2) not null default 0,
  service_area text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.waste_routes (
  id uuid primary key default gen_random_uuid(),
  route_code text unique not null,
  start_location_key text references public.locations(location_key) on delete set null,
  end_location_key text references public.locations(location_key) on delete set null,
  total_distance_km numeric(10,2),
  total_time_min numeric(10,2),
  algorithm text,
  path jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.network_metrics (
  id uuid primary key default gen_random_uuid(),
  location_key text not null unique references public.locations(location_key) on delete cascade,
  degree_centrality numeric(10,4),
  betweenness_centrality numeric(10,4),
  closeness_centrality numeric(10,4),
  pagerank numeric(10,6),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.app_settings (
  id uuid primary key default gen_random_uuid(),
  setting_key text unique not null,
  setting_value jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
