from collections import defaultdict,Counter
from .models import Assignment,Entry,Faculty,Subject,Section,Room,SlotTemplate,Timetable
from .engine import context,validate_entries,candidates
from .configuration import violation,matches

def rows(db,table_id):
    result=[]
    for e in db.query(Entry).filter_by(timetable_id=table_id):
        a=db.get(Assignment,e.assignment_id);subject=db.get(Subject,a.subject_id)
        result.append({'id':e.id,'timetable_id':e.timetable_id,'assignment_id':a.id,'faculty_id':a.faculty_id,'subject_id':a.subject_id,'section_id':a.section_id,'room_id':e.room_id,'day':e.day,'start':e.start,'end':e.end,'codes':e.codes,'periods':a.periods,'kind':subject.kind,'subject':subject.name,'subject_code':subject.code,'faculty':db.get(Faculty,a.faculty_id).name,'section':db.get(Section,a.section_id).name,'room':db.get(Room,e.room_id).name,'difficulty':subject.difficulty})
    return result

def gap_metrics(entries,key):
    groups=defaultdict(list)
    for e in entries: groups[(e[key],e['day'],e['start']<840)].append(e)
    idle=span=0
    for group in groups.values():
        group.sort(key=lambda e:e['start'])
        if not group: continue
        cursor=group[0]['end'];span+=max(e['end'] for e in group)-group[0]['start']
        for e in group[1:]:
            idle+=max(0,e['start']-cursor);cursor=max(cursor,e['end'])
    return idle,round(100*(1-idle/span),1) if span else 100.0

def evaluate(db,entries,complete=True):
    ctx=context(db);issues=[]
    try: enriched=validate_entries(db,entries,complete=complete)
    except ValueError as e:
        issues.append(str(e));enriched=[]
        assignments={a.id:a for a in db.query(Assignment)}
        for entry in entries:
            a=assignments.get(entry['assignment_id'])
            if a: enriched.append(dict(entry,faculty_id=a.faculty_id,section_id=a.section_id,subject_id=a.subject_id,periods=a.periods,difficulty=ctx['subjects'][a.subject_id].difficulty))
    preferred_faculty={w.faculty_id for w in ctx['availability'] if w.status=='preferred'}
    eligible=[e for e in enriched if e['faculty_id'] in preferred_faculty]
    hits=sum(any(w.faculty_id==e['faculty_id'] and w.status=='preferred' and w.day==e['day'] and w.start<=e['start'] and e['end']<=w.end for w in ctx['availability']) for e in eligible)
    preference=100*hits/len(eligible) if eligible else 100
    student_idle,student_gap_score=gap_metrics(enriched,'section_id');faculty_idle,faculty_gap_score=gap_metrics(enriched,'faculty_id')
    repeats=sum(max(0,n-1) for n in Counter((e['subject_id'],e['section_id'],e['day']) for e in enriched).values())
    daily=[]
    for fid in {e['faculty_id'] for e in enriched}:
        loads=[sum(e['periods'] for e in enriched if e['faculty_id']==fid and e['day']==d) for d in sorted(ctx['days'])]
        daily.append(1-(max(loads)-min(loads))/max(loads) if loads and max(loads) else 1)
    distribution=100*(.5*(1-repeats/max(len(enriched),1))+.5*(sum(daily)/len(daily) if daily else 1))
    components={'conflict_free':{'score':0 if issues else 100,'weight':40},'faculty_preference':{'score':round(preference,1),'weight':20},'student_gap_reduction':{'score':student_gap_score,'weight':15},'faculty_gap_reduction':{'score':faculty_gap_score,'weight':15},'balanced_distribution':{'score':round(distribution,1),'weight':10}}
    score=round(sum(c['score']*c['weight']/100 for c in components.values()),1)
    soft=[]
    for c in ctx['constraints']:
        if c.severity=='SOFT':
            amount=sum(violation(c,e) for e in enriched)
            if amount: soft.append({'name':c.name,'violations':amount,'weighted_penalty':amount*c.weight})
    return {'quality_score':score,'components':components,'conflicts':issues,'conflict_count':len(issues),'faculty_satisfaction':round(preference,1),'student_idle_minutes':student_idle,'faculty_idle_minutes':faculty_idle,'repeated_subject_sessions':repeats,'soft_time_rule_violations':soft,'note':'Quality is an explanatory metric (40/20/15/15/10), distinct from the solver objective. Idle gaps exclude lunch but include normal short breaks.'}

def analytics(db,table_id):
    entries=rows(db,table_id);ctx=context(db);result=evaluate(db,entries)
    slots={(s.day,s.system,s.code):s for s in ctx['slots']}
    def contact(e): return sum(slots[(e['day'],e['kind'],code)].end-slots[(e['day'],e['kind'],code)].start for code in e['codes'].split(',') if (e['day'],e['kind'],code) in slots)
    workloads=[]
    for f in ctx['faculty'].values():
        own=[e for e in entries if e['faculty_id']==f.id]
        workloads.append({'id':f.id,'name':f.name,'periods':sum(e['periods'] for e in own),'sessions':len(own),'teaching_minutes':sum(contact(e) for e in own),'max_week':f.max_classes_week,'max_day':f.max_classes_day,'daily_periods':[sum(e['periods'] for e in own if e['day']==d) for d in range(5)]})
    rooms=[]
    for r in ctx['rooms']:
        own=[e for e in entries if e['room_id']==r.id]
        capacity=sum(s.end-s.start for s in ctx['slots'] if s.system==r.kind and s.day in ctx['days'])
        minutes=sum(contact(e) for e in own)
        rooms.append({'id':r.id,'name':r.name,'kind':r.kind,'capacity':r.capacity,'sessions':len(own),'teaching_minutes':minutes,'reserved_minutes':sum(e['end']-e['start'] for e in own),'available_slot_minutes':capacity,'utilization_percent':round(minutes/capacity*100,1) if capacity else 0})
    result.update({'faculty':workloads,'rooms':rooms,'counts':{'faculty':len(ctx['faculty']),'subjects':len(ctx['subjects']),'sections':len(ctx['sections']),'rooms':len(ctx['rooms']),'sessions':len(entries)},'room_utilization':round(sum(r['teaching_minutes'] for r in rooms)/max(1,sum(r['available_slot_minutes'] for r in rooms))*100,1)})
    recommendations=[]
    if result['student_idle_minutes']>60: recommendations.append('Increase the student_gaps soft weight to compact section schedules.')
    if result['faculty_idle_minutes']>60: recommendations.append('Increase the faculty_gaps soft weight to reduce idle faculty time.')
    if result['faculty_satisfaction']<100: recommendations.append('Review preferred windows or increase faculty_preferences weight.')
    if result['repeated_subject_sessions']: recommendations.append('Increase spread_subjects weight to spread subjects across weekdays.')
    for f in workloads:
        if f['periods']>=f['max_week']*.9: recommendations.append(f"{f['name']} is near their weekly limit; consider reassigning some teaching assignments.")
    result['recommendations']=recommendations or ['No major issue detected. Compare another solution before publishing.']
    return result
