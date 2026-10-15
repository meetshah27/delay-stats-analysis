-- Benchmark 3 (parquet): full-table count of cancelled flights.
select count(*) as cancelled_flights
from ontime
where cancelled = 1
