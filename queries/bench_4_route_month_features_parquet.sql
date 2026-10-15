-- Benchmark 4 (parquet): the H3 feature extraction (route-month mean delay and distance,
-- routes with at least 30 flights in the month, 2023 to 2025).
select origin, dest, year, month,
    avg(arrdelay) as mean_arrdelay,
    avg(distance) as distance,
    count(*) as flights
from ontime
where year between 2023 and 2025 and cancelled = 0 and diverted = 0
group by origin, dest, year, month
having count(*) >= 30
