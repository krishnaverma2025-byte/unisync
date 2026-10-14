from collections import defaultdict, Counter
from itertools import combinations
from ortools.sat.python import cp_model
from .models import Assignment, Subject, Section, Room, SlotTemplate, Availability, Entry, Timetable, Faculty, WorkingDay, SchedulingConstraint
from .configuration import violation, matches

class SchedulingFailure(ValueError):
    def __init__(self, message, issues=None, status='INFEASIBLE'):
        super().__init__(message)
        self.detail={'message':message,'status':status,'issues':issues or [],'suggestions':list(dict.fromkeys(i['suggestion'] for i in (issues or []) if i.get('suggestion')))}

def overlaps(a,b):
    return a['day']==b['day'] and a['start']<b['end'] and b['start']<a['end']

def context(db):
    days=db.query(WorkingDay).all()
    return {'subjects':{s.id:s for s in db.query(Subject)},'sections':{s.id:s for s in db.query(Section)},'faculty':{s.id:s for s in db.query(Faculty)},'rooms':db.query(Room).all(),'slots':db.query(SlotTemplate).order_by(SlotTemplate.day,SlotTemplate.period).all(),'availability':db.query(Availability).all(),'constraints':db.query(SchedulingConstraint).filter_by(enabled=True).all(),'days':{d.day for d in days if d.enabled} if days else set(range(5))}

def candidates(db, assignment, ctx=None):
    ctx=ctx or context(db)
    subject=ctx['subjects'][assignment.subject_id]; section=ctx['sections'][assignment.section_id]
    if subject.kind=='THEORY' and assignment.periods!=1: raise ValueError('Theory assignments require one period per session')
    rooms=[r for r in ctx['rooms'] if r.kind==subject.kind and r.capacity>=section.size]
    slots=[s for s in ctx['slots'] if s.system==subject.kind and s.day in ctx['days']]
    windows=[w for w in ctx['availability'] if w.faculty_id==assignment.faculty_id]
    result=[]
    for slot in slots:
        group=sorted([s for s in slots if s.day==slot.day and s.block==slot.block and slot.period<=s.period<slot.period+assignment.periods],key=lambda s:s.period)
        if len(group)!=assignment.periods: continue
        if any(b.period!=a.period+1 or b.start-a.end>11 for a,b in zip(group,group[1:])): continue
        start,end=group[0].start,group[-1].end
        if not any(w.status!='unavailable' and w.day==slot.day and w.start<=start and end<=w.end for w in windows): continue
        if any(w.status=='unavailable' and w.day==slot.day and w.start<end and start<w.end for w in windows): continue
        option=dict(assignment_id=assignment.id,faculty_id=assignment.faculty_id,subject_id=subject.id,section_id=assignment.section_id,day=slot.day,start=start,end=end,codes=','.join(s.code for s in group),periods=assignment.periods,kind=subject.kind,period=slot.period,difficulty=subject.difficulty,preferred=any(w.status=='preferred' and w.day==slot.day and w.start<=start and end<=w.end for w in windows))
        if any(c.severity=='HARD' and violation(c,option) for c in ctx['constraints']): continue
        for room in rooms: result.append(dict(option,room_id=room.id))
    return result

def public_entry(c):
    return {k:c[k] for k in ('assignment_id','room_id','day','start','end','codes')}

def consecutive_windows(options,limit):
    """Sets of THEORY period numbers constituting limit+1 consecutive lectures."""
    periods=sorted({o['period'] for o in options if o['kind']=='THEORY'})
    return [periods[i:i+limit+1] for i in range(len(periods)-limit) if periods[i+limit]-periods[i]==limit]

def validate_entries(db, entries, complete=False):
    ctx=context(db); assignments={a.id:a for a in db.query(Assignment)}
    enriched=[]; counts=Counter(); options_cache={}
    for entry in entries:
        a=assignments.get(entry['assignment_id'])
        if not a: raise ValueError('Unknown teaching assignment')
        options=options_cache.setdefault(a.id,candidates(db,a,ctx))
        keys=('room_id','day','start','end','codes')
        match=next((c for c in options if all(c[k]==entry[k] for k in keys)),None)
        if not match:
            faculty=ctx['faculty'][a.faculty_id]
            raise ValueError(f'{ctx["subjects"][a.subject_id].name}: violates a slot, consecutive lab block, {faculty.name}\'s availability, working day, hard rule, or room type/capacity')
        enriched.append(dict(entry,**{k:v for k,v in match.items() if k not in entry})); counts[a.id]+=1
    for i,a in enumerate(enriched):
        for b in enriched[i+1:]:
            if overlaps(a,b):
                names={'faculty_id':ctx['faculty'][a['faculty_id']].name,'section_id':ctx['sections'][a['section_id']].name,'room_id':next(r.name for r in ctx['rooms'] if r.id==a['room_id'])}
                for key,name in names.items():
                    if a[key]==b[key]: raise ValueError(f'{key.replace("_id","").capitalize()} clash: {name} already has {ctx["subjects"][b["subject_id"]].name} at {b["start"]//60:02d}:{b["start"]%60:02d}–{b["end"]//60:02d}:{b["end"]%60:02d}')
    for a in assignments.values():
        if counts[a.id]>a.weekly_sessions or (complete and counts[a.id]!=a.weekly_sessions): raise ValueError(f'Weekly session count violated for assignment {a.id}: {counts[a.id]}/{a.weekly_sessions}')
    for f in ctx['faculty'].values():
        own=[e for e in enriched if e['faculty_id']==f.id]
        if sum(e['periods'] for e in own)>f.max_classes_week: raise ValueError(f'{f.name}: weekly workload limit exceeded')
        if any(sum(e['periods'] for e in own if e['day']==d)>f.max_classes_day for d in range(5)): raise ValueError(f'{f.name}: daily workload limit exceeded')
    for c in ctx['constraints']:
        if c.severity!='HARD' or c.rule not in ('max_daily_sessions','max_consecutive'): continue
        for d in range(5):
            own=[e for e in enriched if e['day']==d and matches(c,e)]
            for group in grouped(own,c).values():
                if c.rule=='max_daily_sessions' and len(group)>c.value: raise ValueError(f'Hard constraint: {c.name}')
                if c.rule=='max_consecutive' and consecutive_windows(group,c.value): raise ValueError(f'Hard constraint: {c.name}')
    return enriched

def grouped(options,c):
    groups=defaultdict(list)
    # Subject rules apply separately per section; faculty rules per faculty.
    key='section_id' if c.subject_id or c.section_id or c.rule in ('student_gaps','spread_subjects','spread_difficult') else 'faculty_id'
    for option in options: groups[option[key]].append(option)
    return groups

def diagnostics(db,ctx,assignments):
    issues=[]
    for a in assignments:
        subject=ctx['subjects'][a.subject_id]; section=ctx['sections'][a.section_id]; faculty=ctx['faculty'][a.faculty_id]
        options=candidates(db,a,ctx); unique={(o['day'],o['start'],o['end']) for o in options}
        if len(unique)<a.weekly_sessions:
            issues.append({'assignment_id':a.id,'message':f'{subject.name} / {section.name}: {a.weekly_sessions} sessions of {a.periods} period(s) required; only {len(unique)} feasible clock placements for {faculty.name}.','suggestion':'Extend available windows, relax scoped hard rules, enable working days, or add a suitable room.'})
        if not any(r.kind==subject.kind and r.capacity>=section.size for r in ctx['rooms']):
            issues.append({'assignment_id':a.id,'message':f'{subject.name}: no {subject.kind} room can hold {section.size} students.','suggestion':f'Add a {subject.kind} room with capacity at least {section.size}.'})
    for f in ctx['faculty'].values():
        required=sum(a.weekly_sessions*a.periods for a in assignments if a.faculty_id==f.id)
        if required>f.max_classes_week or required>f.max_classes_day*len(ctx['days']):
            issues.append({'faculty_id':f.id,'message':f'{f.name} needs {required} teaching periods; limits are {f.max_classes_day}/day and {f.max_classes_week}/week.','suggestion':'Increase workload limits or reassign teaching assignments to another faculty member.'})
    return issues

def solve(db,count=1,time_limit=15,seed=0):
    assignments=db.query(Assignment).order_by(Assignment.id).all();ctx=context(db)
    if not assignments: raise SchedulingFailure('Add teaching assignments before generation',status='INVALID_INPUT')
    issues=diagnostics(db,ctx,assignments)
    if issues: raise SchedulingFailure('Academic requirements have no feasible placements.',issues)
    model=cp_model.CpModel(); choices=[]; assumption_names={}
    def assumption(message):
        var=model.new_bool_var(f'assumption_{len(assumption_names)}');model.add_assumption(var);assumption_names[var.index]=message;return var
    for a in assignments:
        variables=[]
        for o in candidates(db,a,ctx):
            var=model.new_bool_var(f'a{a.id}_c{len(choices)}');choices.append((o,var));variables.append(var)
        model.add(sum(variables)==a.weekly_sessions).only_enforce_if(assumption(f'{ctx["subjects"][a.subject_id].name} / {ctx["sections"][a.section_id].name}: {a.weekly_sessions} weekly sessions'))
    buckets_by_resource={}
    for resource in ('faculty_id','section_id','room_id'):
        buckets=defaultdict(list)
        for o,v in choices: buckets[(o[resource],o['day'])].append((o,v))
        buckets_by_resource[resource]=buckets
        for key,options in buckets.items():
            resource_name=ctx['faculty'][key[0]].name if resource=='faculty_id' else ctx['sections'][key[0]].name if resource=='section_id' else next(r.name for r in ctx['rooms'] if r.id==key[0])
            a=assumption(f'{resource_name}: no overlapping classes on weekday {key[1]+1}')
            for t in sorted({o['start'] for o,v in options}):
                active=[v for o,v in options if o['start']<=t<o['end']]
                if len(active)>1: model.add(sum(active)<=1).only_enforce_if(a)
    for f in ctx['faculty'].values():
        own=[(o,v) for o,v in choices if o['faculty_id']==f.id]
        model.add(sum(o['periods']*v for o,v in own)<=f.max_classes_week).only_enforce_if(assumption(f'{f.name}: maximum {f.max_classes_week} periods/week'))
        for d in ctx['days']:
            model.add(sum(o['periods']*v for o,v in own if o['day']==d)<=f.max_classes_day).only_enforce_if(assumption(f'{f.name}: maximum {f.max_classes_day} periods on weekday {d+1}'))
    penalties=[]
    bound=sum(a.weekly_sessions*a.periods for a in assignments)
    def excess(expr,threshold,weight,label,severity='SOFT'):
        if severity=='HARD': model.add(expr<=threshold).only_enforce_if(assumption(label))
        else:
            x=model.new_int_var(0,max(bound,12),label);model.add(x>=expr-threshold);penalties.append(x*weight)
    for c in ctx['constraints']:
        own=[(o,v) for o,v in choices if matches(c,o)]
        if c.severity=='SOFT': penalties.extend(violation(c,o)*c.weight*v for o,v in own if violation(c,o))
        if c.rule=='faculty_preferences':
            preferred_faculty={w.faculty_id for w in ctx['availability'] if w.status=='preferred'}
            penalties.extend(c.weight*v for o,v in own if o['faculty_id'] in preferred_faculty and not o['preferred'])
        for d in ctx['days']:
            daily=[(o,v) for o,v in own if o['day']==d]
            groups=defaultdict(list)
            for o,v in daily:
                key=(o['section_id'],o['subject_id']) if c.rule=='spread_subjects' else o['section_id'] if c.rule in ('student_gaps','spread_difficult') or c.subject_id or c.section_id else o['faculty_id']
                groups[key].append((o,v))
            for key,options in groups.items():
                if c.rule in ('max_daily_sessions','spread_subjects','spread_difficult'):
                    selected=[v for o,v in options if c.rule!='spread_difficult' or o['difficulty']>=4]
                    excess(sum(selected),c.value,c.weight,f'{c.name}:{key}:day{d}',c.severity)
                if c.rule=='max_consecutive':
                    for window in consecutive_windows([o for o,v in options],c.value):
                        excess(sum(v for o,v in options if o['kind']=='THEORY' and o['period'] in window),c.value,c.weight,f'{c.name}:{key}:day{d}:period{window[0]}',c.severity)
                if c.rule in ('faculty_gaps','student_gaps'):
                    # Optimize idle minutes within each AM/PM block; never count lunch.
                    for am in (True,False):
                        block=[(o,v) for o,v in options if (o['start']<840)==am]
                        if not block: continue
                        starts=[];ends=[]
                        for o,v in block:
                            st=model.new_int_var(0,1440,'effective_start');en=model.new_int_var(0,1440,'effective_end')
                            model.add(st==o['start']).only_enforce_if(v);model.add(st==1440).only_enforce_if(v.Not())
                            model.add(en==o['end']).only_enforce_if(v);model.add(en==0).only_enforce_if(v.Not());starts.append(st);ends.append(en)
                        first=model.new_int_var(0,1440,'first');last=model.new_int_var(0,1440,'last');gap=model.new_int_var(0,1440,'idle_minutes')
                        model.add_min_equality(first,starts);model.add_max_equality(last,ends)
                        model.add(gap>=last-first-sum((o['end']-o['start'])*v for o,v in block));penalties.append(gap*c.weight)
        if c.rule=='balance_workload':
            faculty_ids={o['faculty_id'] for o,v in own}
            for fid in faculty_ids:
                loads=[sum(o['periods']*v for o,v in own if o['faculty_id']==fid and o['day']==d) for d in sorted(ctx['days'])]
                if not loads: continue
                hi=model.new_int_var(0,bound,'maximum_daily_load');lo=model.new_int_var(0,bound,'minimum_daily_load')
                model.add_max_equality(hi,loads);model.add_min_equality(lo,loads);penalties.append((hi-lo)*c.weight)
    # A low tie-break cost encourages earlier hours without overpowering gap preferences.
    model.minimize(sum(penalties)+sum((o['start']//60)*v for o,v in choices))
    solutions=[]; exhausted=False
    for attempt in range(count):
        solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=time_limit;solver.parameters.num_search_workers=4;solver.parameters.random_seed=seed+attempt
        status=solver.solve(model)
        if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            if solutions: exhausted=True;break
            core=[]
            if status==cp_model.INFEASIBLE:
                core=[{'message':assumption_names.get(i,'Conflicting hard requirements'),'suggestion':'Relax one listed requirement, expand faculty availability, add rooms, or reassign a faculty member.'} for i in solver.sufficient_assumptions_for_infeasibility()]
            raise SchedulingFailure('No feasible timetable exists under these hard requirements.' if status==cp_model.INFEASIBLE else 'The solver reached its time limit before finding a timetable.',core or issues,solver.status_name(status))
        selected=[o for o,v in choices if solver.value(v)]
        entries=[public_entry(o) for o in selected];validate_entries(db,entries,complete=True)
        solutions.append({'entries':entries,'solver_status':solver.status_name(status),'objective':solver.objective_value,'solve_seconds':round(solver.wall_time,3)})
        # Forbid identical clock placements, including variants differing only by room.
        # Ensures the alternatives provide materially different schedules.
        groups={(o['assignment_id'],o['day'],o['start']) for o in selected}
        same=[v for o,v in choices if (o['assignment_id'],o['day'],o['start']) in groups]
        model.add(sum(same)<=len(selected)-1)
    return solutions,exhausted

def generate(db,name):
    solutions,_=solve(db)
    solution=solutions[0]
    table=Timetable(name=name,solver_status=solution['solver_status']);db.add(table);db.flush()
    db.add_all(Entry(timetable_id=table.id,**e) for e in solution['entries']);db.commit();return table
