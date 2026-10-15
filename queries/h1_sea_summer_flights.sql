-- H1: arrival delays of completed flights arriving at SEA, June to August 2023 and 2024.
select year, flightdate, arrdelay
from ontime
where dest = 'SEA'
    and year in (2023, 2024)
    and month between 6 and 8
    and cancelled = 0
    and diverted = 0
    and arrdelay is not null
