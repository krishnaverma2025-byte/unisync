from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,Field
from .db import get_db
from .auth import current_user,admin
from .models import *
from .engine import solve,SchedulingFailure,validate_entries,candidates,context,overlaps,diagnostics,public_entry
from .analytics import rows,analytics,evaluate
from .configuration import check_constraint
from .natural_language import parse
from .exports import export_pdf,export_xlsx

router=APIRouter()
def dump(row): return {c.name:getattr(row,c.name) for c in row.__table__.columns if c.name!='password_hash'}
def get(db,model,id):
    row=db.get(model,id)
    if not row: raise HTTPException(404,'Record not found')
    return row
def visible(db,id,user):
    table=get(db,Timetable,id)
    if user.role!='admin' and not table.published: raise HTTPException(403,'Draft timetable')
    return table
@router.get('/academic-options')
def academic_options(user=Depends(current_user),db=Depends(get_db)):
    return {'courses':[dump(r) for r in db.query(Course)],'semesters':[dump(r) for r in db.query(Semester)],'sections':[dump(r) for r in db.query(Section)],'faculty':[dump(r) for r in db.query(Faculty)],'rooms':[dump(r) for r in db.query(Room)]}
class SectionSelection(BaseModel):
    section_id:int|None
@router.put('/student/section')
def student_section(data:SectionSelection,user=Depends(current_user),db=Depends(get_db)):
    if user.role!='student': raise HTTPException(403,'Student role required')
    if data.section_id is not None: get(db,Section,data.section_id)
    user.section_id=data.section_id;db.commit();return dump(user)
@router.get('/timetables/{id}/view')
def timetable_view(id:int,view:Literal['section','faculty','room']='section',entity_id:int|None=None,user=Depends(current_user),db=Depends(get_db)):
    table=visible(db,id,user);entries=rows(db,id)
    if entity_id is not None: entries=[e for e in entries if e[view+'_id']==entity_id]
    return dict(dump(table),view=view,entries=entries)
@router.get('/timetables/{id}/analytics')
def timetable_analytics(id:int,user=Depends(current_user),db=Depends(get_db)):
    visible(db,id,user);return analytics(db,id)
@router.get('/timetables/{id}/export/{format}')
def download(id:int,format:Literal['pdf','xlsx'],view:Literal['section','faculty','room']='section',entity_id:int|None=None,user=Depends(current_user),db=Depends(get_db)):
    table=visible(db,id,user);entries=rows(db,id)
    if entity_id is not None: entries=[e for e in entries if e[view+'_id']==entity_id]
    title=table.name+(f' · {view} {entity_id}' if entity_id else '')
    content=export_pdf(title,entries) if format=='pdf' else export_xlsx(title,entries)
    media='application/pdf' if format=='pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return Response(content,media_type=media,headers={'Content-Disposition':f'attachment; filename="unisync-{id}-{view}.{format}"'})
class RoomQuery(BaseModel):
    day:int=Field(ge=0,le=4)
    start:int=Field(ge=0,le=1439)
    end:int=Field(ge=1,le=1440)
    kind:Literal['THEORY','LAB']|None=None
    capacity:int=Field(default=1,ge=1)
    timetable_id:int|None=None
@router.post('/free-rooms')
def free_rooms(data:RoomQuery,user=Depends(current_user),db=Depends(get_db)):
    if data.start>=data.end: raise HTTPException(422,'End must follow start')
    table=visible(db,data.timetable_id,user) if data.timetable_id else db.query(Timetable).filter_by(published=True).order_by(Timetable.id.desc()).first()
    if not table: raise HTTPException(404,'No published timetable; select a draft as administrator')
    unavailable={e.room_id for e in db.query(Entry).filter_by(timetable_id=table.id,day=data.day) if e.start<data.end and data.start<e.end}
    rooms=db.query(Room).filter(Room.capacity>=data.capacity)
    if data.kind: rooms=rooms.filter_by(kind=data.kind)
    return {'timetable_id':table.id,'rooms':[dump(r) for r in rooms if r.id not in unavailable]}
class Alternatives(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    count:int=Field(default=3,ge=1,le=5)
    time_limit:int=Field(default=5,ge=1,le=20)
@router.post('/admin/alternatives')
def alternatives(data:Alternatives,user=Depends(admin),db=Depends(get_db)):
    try: solutions,exhausted=solve(db,data.count,data.time_limit)
    except SchedulingFailure as e: raise HTTPException(422,e.detail)
    summaries=[]
    # Persist all variants in one transaction only after all solver outputs validate.
    for index,s in enumerate(solutions,1):
        table=Timetable(name=f'{data.name} · Option {index}',solver_status=s['solver_status']);db.add(table);db.flush()
        db.add_all(Entry(timetable_id=table.id,**e) for e in s['entries'])
        score=evaluate(db,s['entries'])
        summaries.append(dict(dump(table),quality=score,objective=s['objective'],solve_seconds=s['solve_seconds']))
    db.commit();summaries.sort(key=lambda s:(-s['quality']['quality_score'],s['objective']))
    return {'best_id':summaries[0]['id'],'alternatives':summaries,'exhausted':exhausted,'note':'Alternatives have distinct class clock placements. Highest explanatory quality score is recommended for admin review; nothing is auto-published.'}
@router.get('/admin/diagnostics')
def diagnose(user=Depends(admin),db=Depends(get_db)):
    assignments=db.query(Assignment).all();ctx=context(db)
    return {'issues':diagnostics(db,ctx,assignments),'assignment_count':len(assignments),'candidate_counts':[{'assignment_id':a.id,'placements':len({(c['day'],c['start'],c['end']) for c in candidates(db,a,ctx)})} for a in assignments],'note':'These are preflight checks. If globally incompatible, generation reports a solver assumption core; it may not be the smallest conflicting set.'}
@router.get('/admin/entries/{id}/options')
def entry_options(id:int,user=Depends(admin),db=Depends(get_db)):
    entry=get(db,Entry,id);assignment=get(db,Assignment,entry.assignment_id)
    return [public_entry(c) for c in candidates(db,assignment)]
class Move(BaseModel):
    entry_id:int
    day:int=Field(ge=0,le=4)
    start:int=Field(ge=0,le=1439)
    room_id:int

def checked_move(db,data):
    entry=get(db,Entry,data.entry_id);table=get(db,Timetable,entry.timetable_id)
    if table.published: raise HTTPException(409,'Unpublish before editing; publish again after review')
    assignment=get(db,Assignment,entry.assignment_id)
    candidate=next((c for c in candidates(db,assignment) if c['day']==data.day and c['start']==data.start and c['room_id']==data.room_id),None)
    if not candidate: raise HTTPException(422,'No valid slot/lab block at this time. Check room type/capacity, availability and hard constraints.')
    others=[dump(e) for e in db.query(Entry).filter_by(timetable_id=table.id) if e.id!=entry.id]
    try: validate_entries(db,others+[public_entry(candidate)],complete=True)
    except ValueError as e: raise HTTPException(409,str(e))
    return entry,candidate
@router.post('/admin/validate-change')
def validate_change(data:Move,user=Depends(admin),db=Depends(get_db)):
    _,candidate=checked_move(db,data);return {'valid':True,'entry':public_entry(candidate)}
@router.put('/admin/entries/{id}/move')
def move_entry(id:int,data:Move,user=Depends(admin),db=Depends(get_db)):
    if data.entry_id!=id: raise HTTPException(422,'Entry ID mismatch')
    entry,candidate=checked_move(db,data)
    for k,v in public_entry(candidate).items(): setattr(entry,k,v)
    db.commit();return dump(entry)
@router.get('/faculty/workload')
def faculty_workload(timetable_id:int|None=None,user=Depends(current_user),db=Depends(get_db)):
    faculty=db.query(Faculty).filter_by(user_id=user.id).first()
    if not faculty: raise HTTPException(403,'No linked faculty profile')
    table=visible(db,timetable_id,user) if timetable_id else db.query(Timetable).filter_by(published=True).order_by(Timetable.id.desc()).first()
    if not table: return {'timetable_id':None,'faculty':dump(faculty),'workload':None,'entries':[]}
    stats=analytics(db,table.id)
    return {'timetable_id':table.id,'faculty':dump(faculty),'workload':next(f for f in stats['faculty'] if f['id']==faculty.id),'entries':[e for e in rows(db,table.id) if e['faculty_id']==faculty.id]}
class RequestInput(BaseModel):
    timetable_id:int
    entry_id:int|None=None
    reason:str=Field(min_length=5,max_length=2000)
@router.post('/change-requests')
def submit_request(data:RequestInput,user=Depends(current_user),db=Depends(get_db)):
    if user.role!='faculty': raise HTTPException(403,'Faculty role required')
    f=db.query(Faculty).filter_by(user_id=user.id).first()
    if not f: raise HTTPException(403,'No linked faculty profile')
    visible(db,data.timetable_id,user)
    if data.entry_id:
        e=get(db,Entry,data.entry_id);a=get(db,Assignment,e.assignment_id)
        if e.timetable_id!=data.timetable_id or a.faculty_id!=f.id: raise HTTPException(403,'Request a change to your own class')
    r=ChangeRequest(user_id=user.id,**data.model_dump());db.add(r);db.commit();return dump(r)
@router.get('/change-requests')
def requests(user=Depends(current_user),db=Depends(get_db)):
    query=db.query(ChangeRequest)
    if user.role!='admin': query=query.filter_by(user_id=user.id)
    return [dict(dump(r),requester=db.get(User,r.user_id).name) for r in query.order_by(ChangeRequest.id.desc())]
class Review(BaseModel):
    status:Literal['approved','rejected']
    admin_note:str=Field(default='',max_length=2000)
@router.patch('/admin/change-requests/{id}')
def review_request(id:int,data:Review,user=Depends(admin),db=Depends(get_db)):
    r=get(db,ChangeRequest,id);r.status=data.status;r.admin_note=data.admin_note;db.commit();return dump(r)
class NaturalText(BaseModel):
    text:str=Field(min_length=1,max_length=3000)
@router.post('/admin/constraints/parse')
def parse_constraints(data:NaturalText,user=Depends(admin),db=Depends(get_db)):
    return parse(db,data.text)
class RuleInput(BaseModel):
    name:str=Field(min_length=1,max_length=200)
    severity:Literal['HARD','SOFT']='SOFT'
    rule:str
    faculty_id:int|None=None
    subject_id:int|None=None
    section_id:int|None=None
    value:int=0
    weight:int=Field(default=100,ge=0,le=1000)
    enabled:bool=True
class RuleBatch(BaseModel):
    constraints:list[RuleInput]=Field(min_length=1,max_length=20)
@router.post('/admin/constraints/batch')
def save_rules(data:RuleBatch,user=Depends(admin),db=Depends(get_db)):
    saved=[]
    for r in data.constraints:
        c=SchedulingConstraint(**r.model_dump())
        for model,key in ((Faculty,'faculty_id'),(Subject,'subject_id'),(Section,'section_id')):
            if getattr(c,key) is not None: get(db,model,getattr(c,key))
        try: check_constraint(c)
        except ValueError as e: raise HTTPException(422,str(e))
        saved.append(c)
    db.add_all(saved);db.flush()
    try:
        for table in db.query(Timetable).filter_by(published=True): validate_entries(db,[dump(e) for e in db.query(Entry).filter_by(timetable_id=table.id)],complete=True)
    except ValueError as e:
        db.rollback();raise HTTPException(409,'This would invalidate a published timetable: '+str(e))
    db.commit();return [dump(c) for c in saved]
