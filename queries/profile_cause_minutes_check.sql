-- Data profile: for flights delayed 15+ minutes, do the five cause columns add up to the
-- arrival delay? Share within 1 minute, and the mean absolute gap.
select
    count(*) as delayed_flights,
    avg(case when abs((coalesce(carrierdelay, 0) + coalesce(weatherdelay, 0) + coalesce(nasdelay, 0) + coalesce(securitydelay, 0) + coalesce(lateaircraftdelay, 0)) - arrdelay) <= 1 then 1.0 else 0.0 end) as share_within_1_minute,
    avg(abs((coalesce(carrierdelay, 0) + coalesce(weatherdelay, 0) + coalesce(nasdelay, 0) + coalesce(securitydelay, 0) + coalesce(lateaircraftdelay, 0)) - arrdelay)) as mean_abs_gap_minutes
from ontime
where arrdel15 = 1 and cancelled = 0 and diverted = 0
