-- Benchmark 3 (csv): full-table count of cancelled flights.
select count(*) as cancelled_flights
from ontime_csv
where try_cast(cancelled as double) = 1
