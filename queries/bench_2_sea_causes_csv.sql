-- Benchmark 2 (csv): delay minutes by cause for flights arriving at SEA, all months.
select
    sum(try_cast(carrierdelay as double)) as carrierdelay_minutes,
    sum(try_cast(weatherdelay as double)) as weatherdelay_minutes,
    sum(try_cast(nasdelay as double)) as nasdelay_minutes,
    sum(try_cast(securitydelay as double)) as securitydelay_minutes,
    sum(try_cast(lateaircraftdelay as double)) as lateaircraftdelay_minutes
from ontime_csv
where dest = 'SEA'
