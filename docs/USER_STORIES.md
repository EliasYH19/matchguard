# User stories / backlog

Written the same way we did it in the CI/CD lab (Task 1) before writing any
code - kept here for the record rather than deleted once the sprint moved on.

## Backlog

1. As a **tournament organizer**, I want to browse anti-cheat packages and their prices, so that I can pick the right tier for my event size. *(Sprint 1)*
2. As a **tournament organizer**, I want to create a tournament and attach a package to it, so that I can start collecting registrations. *(Sprint 1)*
3. As a **tournament organizer**, I want to pay for the selected package, so that the tournament goes live and can accept scans. *(Sprint 1)*
4. As a **player**, I want to register for a tournament with my gamertag and email, so that I'm on the organizer's roster. *(Sprint 1)*
5. As a **player**, I want to upload a system/process log, so that I get verified before the tournament starts. *(Sprint 1)*
6. As the **platform**, I want to scan an uploaded file against known cheat signatures and hashes, so that flagged players are caught automatically. *(Sprint 1)*
7. As a **tournament organizer**, I want a dashboard listing every flagged player across my tournaments, so that I can act before the bracket locks. *(Sprint 2)*
8. As a **player**, I want a downloadable certificate once my scan comes back clear, so that I have proof of verification. *(Sprint 2)*
9. As a **tournament organizer**, I want to upload a banner image for my tournament, so that the listing looks professional. *(Sprint 2)*
10. As a **platform operator**, I want certificate generation to run as a separate serverless function, so that it scales independently of the always-on API containers. *(Sprint 2)*

## Sprint 1 scope

Stories 1 through 6, the minimum path from "organizer signs up" to "player gets a
verdict". Everything needed to demo the core value proposition end to end.

## Sprint 2 scope

Stories 7 through 10, the organizer-facing dashboard, certificates, banner images
and moving certificate generation into the serverless function.

Elias
