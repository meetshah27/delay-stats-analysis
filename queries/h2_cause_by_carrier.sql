-- H2: primary delay cause by carrier for completed flights delayed 15+ minutes,
-- January 2023 to December 2025 (NONE and TIE kept here; the notebook drops and counts them).
select reporting_airline, primary_delay_cause, count(*) as flights
from ontime
where year between 2023 and 2025
    and arrdel15 = 1
    and cancelled = 0
    and diverted = 0
group by reporting_airline, primary_delay_cause
