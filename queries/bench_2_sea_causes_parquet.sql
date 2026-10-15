-- Benchmark 2 (parquet): delay minutes by cause for flights arriving at SEA, all months.
select
    sum(carrierdelay) as carrierdelay_minutes,
    sum(weatherdelay) as weatherdelay_minutes,
    sum(nasdelay) as nasdelay_minutes,
    sum(securitydelay) as securitydelay_minutes,
    sum(lateaircraftdelay) as lateaircraftdelay_minutes
from ontime
where dest = 'SEA'
