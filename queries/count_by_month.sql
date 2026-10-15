-- Rows per month in the curated table; compared with the source file line counts
-- (data/ingest_log.csv) by `make verify-counts`.
select year, month, count(*) as row_count
from ontime
group by year, month
order by year, month
