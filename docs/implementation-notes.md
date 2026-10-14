# Data and interval conventions

All times are integer minutes after midnight in the campus's local wall-clock time. The MVP has a recurring weekday calendar: Monday 0 through Friday 4. The authoritative screenshot is retained beside this document. Slots carry their system, code, paired display label, ordinal period and AM/PM block.

An import is atomic: validate every code before replacing registrations. A theory code can occur on multiple weekdays, so A1 expands to all its occurrences. Lab L1–L60 identify single occurrences. Busy time is the union of imported occurrences, the user's active published section timetable, weekly personal events and meetup membership. Common free time is the complement of the combined busy union within the requested clock window, filtered by duration; results are ordered chronologically. Lunch is not automatically busy.

Clashes use `[start,end)` overlap, never matching period numbers. Two theory and lab rows can have the same printed cell label but different starts and ends. A multi-period lab session occupies its entire span, including any short internal break, and cannot cross the morning/afternoon block boundary. Availability must cover the entire candidate span.

Scheduling input CRUD revalidates all published timetables and rolls back invalidating changes. Unpublish the affected version before changing hard inputs. Drafts may become invalid and must be reviewed or regenerated before publishing. Entries themselves can be edited in drafts, but every edit must match a valid candidate and avoid resource overlap. Publishing requires all weekly assignment counts to be met.

The SQLite fallback enables foreign keys; PostgreSQL uses the same SQLAlchemy models. Startup applies the additive v1→v2 migration; subsequent field changes need additional versioned migrations. Use a migration tool before persistent production use.
