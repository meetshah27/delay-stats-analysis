-- Benchmark 4 (csv): the H3 feature extraction (route-month mean delay and distance,
-- routes with at least 30 flights in the month, 2023 to 2025).
select origin, dest, year, month,
    avg(try_cast(arrdelay as double)) as mean_arrdelay,
    avg(try_cast(distance as double)) as distance,
    count(*) as flights
from ontime_csv
where year between 2023 and 2025 and try_cast(cancelled as double) = 0 and try_cast(diverted as double) = 0
group by origin, dest, year, month
having count(*) >= 30
