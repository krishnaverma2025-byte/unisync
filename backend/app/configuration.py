from .models import WorkingDay, SchedulingConstraint, Course, Semester, Section, Department
RULES = {'start_after','end_before','am_only','pm_only','avoid_first','avoid_last','max_daily_sessions','spread_subjects','faculty_gaps','student_gaps','balance_workload','max_consecutive','spread_difficult','faculty_preferences'}
HARD_RULES = {'start_after','end_before','am_only','pm_only','avoid_first','avoid_last','max_daily_sessions','max_consecutive'}
DEFAULTS = [('spread_subjects',100,1),('faculty_gaps',2,0),('student_gaps',3,0),('balance_workload',50,0),('max_consecutive',100,3),('spread_difficult',100,1),('avoid_last',20,0),('faculty_preferences',80,0)]
def initialize(db):
    if not db.query(WorkingDay).first():
        db.add_all(WorkingDay(day=day,enabled=True) for day in range(5))
    db.commit()
def seed_preferences(db):
    if db.query(SchedulingConstraint).first(): return
    for rule,weight,value in DEFAULTS:
        db.add(SchedulingConstraint(name='Default '+rule.replace('_',' '),rule=rule,severity='SOFT',weight=weight,value=value))
    db.commit()
def check_constraint(c):
    if c.rule not in RULES: raise ValueError('Unsupported rule: '+str(c.rule))
    if c.severity=='HARD' and c.rule not in HARD_RULES: raise ValueError('This rule is an optimization preference; use SOFT')
    if c.rule in ('start_after','end_before') and not 0<=c.value<=1440: raise ValueError('Time thresholds must be minutes after midnight, 0–1440')
    if c.rule in ('max_daily_sessions','max_consecutive','spread_subjects','spread_difficult') and not 1<=c.value<=12: raise ValueError('This rule requires a threshold from 1 to 12')
    if c.weight is None or not 0<=c.weight<=1000: raise ValueError('Weights must be 0–1000')
def matches(c, option):
    return all(getattr(c,k) is None or getattr(c,k)==option[k] for k in ('faculty_id','subject_id','section_id'))
def violation(c,o):
    if not matches(c,o): return 0
    if c.rule=='start_after': return int(o['start']<c.value)
    if c.rule=='end_before': return int(o['end']>c.value)
    if c.rule=='am_only': return int(o['start']>=840)
    if c.rule=='pm_only': return int(o['start']<840)
    if c.rule=='avoid_first': return int(o['start']==480)
    if c.rule=='avoid_last': return int(o['end']>=1160)
    return 0
