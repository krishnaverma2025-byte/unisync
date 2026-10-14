# Feature guide

The uploaded timetable screenshot still defines every slot. The example period times in the pasted feature roadmap have not replaced it.

## Academic planning

Academic data now includes departments, courses, semesters, sections, faculty, subjects, rooms/labs, working days, slot templates, availability, teaching assignments, constraints, users and timetable entries. Sections can reference a course semester. Subjects have credits and difficulty (1–5; 4–5 count as difficult). Weekly requirements are defined per teaching assignment: `weekly_sessions × periods` gives teaching periods per week. A two-period lab is one session, two teaching periods.

Faculty have `max_classes_day` and `max_classes_week`, measured as teaching periods. Both are hard limits. Availability windows support `available`, `preferred`, `unavailable`. Unavailable wins over an overlapping available/preferred window. Each complete session must fit inside one available/preferred window. No available windows means unavailable.

Working days enable/disable scheduling on the authoritative Monday–Friday template. Disabling days does not delete or change the image-derived slot codes.

## Configurable rules

Every constraint has a name, severity, rule, optional faculty/subject/section scope, threshold `value`, weight (0–1000) and enabled flag. Multiple scopes are an intersection. No scope means global. Threshold clocks use minutes after midnight.

| Rule | Meaning | Allowed severity |
|---|---|---|
| start_after | Class must start at/after value | HARD or SOFT |
| end_before | Class must finish at/before value | HARD or SOFT |
| am_only / pm_only | Prefer/require morning or afternoon block | HARD or SOFT |
| avoid_first | Avoid start at 08:00 | HARD or SOFT |
| avoid_last | Avoid sessions ending at/after 19:20 | HARD or SOFT |
| max_daily_sessions | Maximum sessions/day within scope | HARD or SOFT |
| max_consecutive | Maximum consecutive THEORY period codes | HARD or SOFT |
| spread_subjects | Penalize same subject's sessions beyond value on one section/day | SOFT |
| faculty_gaps | Minimize faculty idle clock minutes within AM/PM blocks | SOFT |
| student_gaps | Minimize section idle clock minutes within AM/PM blocks | SOFT |
| balance_workload | Reduce each faculty member's largest/smallest daily teaching load difference | SOFT |
| spread_difficult | Penalize difficult-subject sessions beyond value per section/day | SOFT |
| faculty_preferences | Favor fully covered preferred availability windows | SOFT |

Consecutive THEORY periods cannot bridge a missing period or lunch. Labs preserve the original consecutive-period candidate rules. Workload balancing distributes already-assigned teaching across weekdays; it does not automatically change the faculty assigned to a subject.

Default soft rules are seeded once for subject distribution, gap reduction, balanced daily workload, consecutive-lecture reduction, difficult subjects, last hours and faculty preferences. Disable, update or delete rules to choose your priorities. Weights belong to the solver's penalty objective.

## AI timetable generator

Generate 2–5 distinct alternatives with a per-option solve budget. Alternatives must differ in at least one class clock placement, not merely swap equivalent rooms. Each output passes hard validation, is saved as a draft and gets an explanatory quality score. The highest quality is recommended; it is never auto-published. More time may improve the solver objective. A feasible result is not a proof of optimality.

The explanatory quality weights are conflict-free 40%, preferred faculty windows 20%, student gap reduction 15%, faculty gap reduction 15%, balanced distribution 10%. When no preferred windows are declared, the preference component is neutral at 100%; it does not imply that preferences were collected. The score is computed from the actual timetable and differs from the solver objective. Balanced distribution combines same-subject repetition reduction and daily workload balance. Idle metrics exclude lunch but include normal short breaks. A reported validation issue prevents publication.

Preflight reports assignments with too few legal clock placements, missing room type/capacity, and excessive faculty requirements. A proven global infeasibility reports a sufficient set of actual solver assumptions; this set is not guaranteed minimal. Timeouts are labelled separately and are not presented as proof that a schedule is impossible.

## Manual editor and publication

In College timetable, choose a draft and select a class card. Use the placement and room selectors, or drag the card onto an available target. Targets already match slots, consecutive labs and faculty availability. The server checks faculty/room/section overlap, daily/weekly load, hard rules and exact weekly counts before accepting the move. A rejected move leaves the database unchanged. Unpublish before editing a published timetable.

Scheduling input changes no longer require deleting all timetables. Each change is checked against all published versions; a change that invalidates one is rejected. Unpublish that version before changing hard inputs, then edit/regenerate and publish again. Drafts may become invalid when hard inputs change; analytics and publication validation expose that state.

## Views, analytics and exports

College timetable has section, faculty and room filters, PDF/Excel downloads for the selected view, room utilization charts, faculty daily workload charts, component quality scores and actionable recommendations. Utilization is teaching-contact minutes divided by the room type's available slot minutes on enabled working days. Multi-period lab internal breaks are reserved for clashes but do not inflate contact minutes.

AI timetable generator includes a free-room finder, comparing actual overlapping intervals with the latest published timetable and filtering room type and minimum seats. This is an availability lookup, not a room booking service.

Students can choose course, semester and section in College timetable, or keep manual code imports only. Their published section entries join imported codes, personal events and meetups in the common-free calculation. Repeated overlaps are merged.

Faculty's Teaching desk shows their published classes, teaching workload and change-request form. Coordinators review requests in AI timetable generator and respond with approve/reject and a note. Approval records the decision; a coordinator must still make the actual draft change and republish.

## Plain-language rules

The local parser previews structured constraints for supported patterns, including:

- `Dr. Meera should preferably have no classes after 3 PM`
- `Programming Lab should happen in the morning`
- `CSE-A maximum 3 sessions per day`
- `everyone should avoid first period classes`

Use saved names/codes; `everyone`/`all` explicitly indicates a global rule. Unsupported or ambiguous clauses return warnings and are not applied. The preview must be reviewed and saved before affecting generation. “Preferably”, “try” or “ideally” makes a SOFT rule; other supported wording is HARD.

This is an offline pattern parser, not an LLM. It needs no API key and sends no text outside the local app. General-purpose generative interpretation is not part of this build.

## Upgrade

Startup runs the additive v1→v2 migration in `app/migrations.py`. Existing accounts, registrations, events, friendships, timetable versions and entries are preserved. `python -m app.seed` adds missing v2 demo course/semester/default preferences idempotently without resetting users. A pre-upgrade backup was saved in the workspace's `work/upgrade-backup` directory. Export dependencies were added to `requirements.txt`; run `pip install -r requirements.txt` when moving an existing installation.
