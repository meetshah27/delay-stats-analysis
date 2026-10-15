-- H3: route-months (origin, dest, year, month) with at least 30 completed flights,
-- January 2023 to December 2025. Congestion = scheduled departures at the origin that month,
-- counting every scheduled flight including cancelled ones.
with origin_month as (
    select origin, year, month, count(*) as scheduled_departures
    from ontime
    where year between 2023 and 2025
    group by origin, year, month
),
route_month as (
    select origin, dest, year, month,
        avg(cast(arrdelay as double)) as mean_arrdelay,
        avg(cast(distance as double)) as distance,
        count(*) as flights
    from ontime
    where year between 2023 and 2025
        and cancelled = 0
        and diverted = 0
        and arrdelay is not null
    group by origin, dest, year, month
    having count(*) >= 30
)
select r.origin, r.dest, r.year, r.month, r.mean_arrdelay, r.distance, r.flights,
    o.scheduled_departures
from route_month r
join origin_month o
    on r.origin = o.origin and r.year = o.year and r.month = o.month
