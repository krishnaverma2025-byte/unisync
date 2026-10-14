"""Local, explainable constraint parser; no external service or LLM dependency.
Unsupported/ambiguous clauses produce warnings and are never silently applied.
"""
import re
from .models import Faculty,Subject,Section

def parse(db,text):
    rules=[];warnings=[]
    for clause in re.split(r';|\n|\s+and\s+',text,flags=re.I):
        clause=clause.strip(' .');lower=clause.lower()
        if not clause: continue
        scopes={}
        for model,key in ((Faculty,'faculty_id'),(Subject,'subject_id'),(Section,'section_id')):
            found=[row for row in db.query(model) if row.name.lower() in lower or (model==Subject and row.code.lower() in lower)]
            if len(found)>1:
                warnings.append(f'Ambiguous {key.replace("_id","")} in: {clause}');scopes=None;break
            if found: scopes[key]=found[0].id
        if scopes is None: continue
        rule=None;value=0
        clock=re.search(r'\b(before|after)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b',lower)
        if clock:
            direction,hour,minute,suffix=clock.groups();hour=int(hour);minute=int(minute or 0)
            if minute>59 or (suffix and not 1<=hour<=12) or (not suffix and hour>23):
                warnings.append(f'Invalid clock time in: {clause}');continue
            if suffix: hour=hour%12+(12 if suffix=='pm' else 0)
            value=hour*60+minute
            rule='end_before' if direction=='after' else 'start_after'
            # "no classes after 3 PM" -> end_before; "prefer classes after" -> start_after.
            negative=bool(re.search(r'\b(no|not|avoid|never)\b',lower))
            if not negative: rule='start_after' if direction=='after' else 'end_before'
        elif re.search(r'\b(morning|afternoon)\b',lower): rule='am_only' if 'morning' in lower else 'pm_only'
        elif 'first' in lower and ('period' in lower or 'class' in lower): rule='avoid_first'
        elif 'last' in lower and ('period' in lower or 'class' in lower): rule='avoid_last'
        elif (m:=re.search(r'(?:maximum|max|at most)\s+(\d+)\s+(?:classes|sessions).*?(?:day|daily)',lower)):
            rule='max_daily_sessions';value=int(m.group(1))
        if not rule:
            warnings.append(f'Unsupported clause: {clause}. Try a named faculty/subject/section with before/after a clock time, morning/afternoon, avoid first/last period, or maximum N sessions per day.');continue
        # Named person/subject text must be matched; an unmatched name must not
        # accidentally create a global rule. Only explicit "everyone/all" is global.
        if not scopes and not re.search(r'\b(everyone|all|global)\b',lower):
            warnings.append(f'No recognized faculty, subject or section in: {clause}. Use its exact saved name/code, or explicitly say everyone.');continue
        severity='SOFT' if re.search(r'prefer|try|ideally',lower) else 'HARD'
        rules.append({'name':clause,'severity':severity,'rule':rule,'value':value,'weight':100,'enabled':True,'faculty_id':scopes.get('faculty_id'),'subject_id':scopes.get('subject_id'),'section_id':scopes.get('section_id')})
    return {'constraints':rules,'warnings':warnings,'parser':'local_supported_patterns','note':'Review structured rules before saving. This local parser supports the documented patterns; it is not an LLM.'}
