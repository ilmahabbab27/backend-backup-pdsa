select *
from public.network_metrics
order by pagerank desc nulls last;

select *
from public.network_metrics
where location_key = $1;

select l.location_key, l.name, l.type, n.degree_centrality, n.betweenness_centrality, n.closeness_centrality, n.pagerank
from public.locations l
left join public.network_metrics n on n.location_key = l.location_key
order by coalesce(n.pagerank, 0) desc, l.name asc;
