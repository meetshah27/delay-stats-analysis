-- Data profile: flights, cancellation and diversion rates per month.
select year, month,
    count(*) as flights,
    avg(cast(cancelled as double)) as cancellation_rate,
    avg(cast(diverted as double)) as diversion_rate
from ontime
group by year, month
order by year, month
