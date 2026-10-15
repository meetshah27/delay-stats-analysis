-- H1 caveat: cancellation and diversion rates for flights arriving at SEA, June to August,
-- so a delay change can be read next to a service change.
select year,
    count(*) as scheduled_flights,
    avg(cast(cancelled as double)) as cancellation_rate,
    avg(cast(diverted as double)) as diversion_rate
from ontime
where dest = 'SEA' and year in (2023, 2024) and month between 6 and 8
group by year
order by year
