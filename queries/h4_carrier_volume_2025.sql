-- H4: carriers by total scheduled flights in 2025 (the top 8 are tested).
select reporting_airline, count(*) as flights
from ontime
where year = 2025
group by reporting_airline
order by flights desc
