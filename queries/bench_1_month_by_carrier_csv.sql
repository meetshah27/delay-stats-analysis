-- Benchmark 1 (csv): mean arrival delay by carrier for one month (partition pruning).
select reporting_airline, avg(try_cast(arrdelay as double)) as mean_arrdelay, count(*) as flights
from ontime_csv
where year = 2024 and month = 7
group by reporting_airline
order by reporting_airline
