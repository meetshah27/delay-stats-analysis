-- H4: arrival delays of completed flights in 2025, by carrier.
select reporting_airline, arrdelay
from ontime
where year = 2025
    and cancelled = 0
    and diverted = 0
    and arrdelay is not null
