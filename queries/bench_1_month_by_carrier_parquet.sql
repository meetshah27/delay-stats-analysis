-- Benchmark 1 (parquet): mean arrival delay by carrier for one month (partition pruning).
select reporting_airline, avg(arrdelay) as mean_arrdelay, count(*) as flights
from ontime
where year = 2024 and month = 7
group by reporting_airline
order by reporting_airline
