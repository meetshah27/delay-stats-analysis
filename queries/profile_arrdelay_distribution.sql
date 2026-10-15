-- Data profile: arrival delay distribution (minutes) for flights that were not cancelled or
-- diverted.
select arrdelay, count(*) as flights
from ontime
where cancelled = 0 and diverted = 0 and arrdelay is not null
group by arrdelay
order by arrdelay
