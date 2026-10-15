-- Data profile: carriers by volume, with their share of flights delayed 15+ minutes.
select reporting_airline,
    count(*) as flights,
    avg(cast(arrdel15 as double)) as delayed_15_share
from ontime
where cancelled = 0 and diverted = 0
group by reporting_airline
order by flights desc
