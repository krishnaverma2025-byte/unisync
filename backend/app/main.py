import os
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, create_model, ConfigDict
from sqlalchemy import Integer, Boolean, or_
from sqlalchemy.exc import IntegrityError
from .db import Base, engine, get_db
from .models import *
from .auth import passwords, token, current_user, admin
from .slots import map_codes, DAYS, BOUNDARIES
from .engine import generate, validate_entries, SchedulingFailure
from .social import busy_for, common_free, shared_users

@asynccontextmanager
async def lifespan(app):
    from .migrations import migrate
    from .configuration import initialize, seed_preferences
    from .db import SessionLocal
    upgraded = migrate(engine)
    with SessionLocal() as db:
        initialize(db)
        if upgraded: seed_preferences(db)
    yield
app=FastAPI(title='UniSync',version='0.2.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(','),allow_credentials=False,allow_methods=['*'],allow_headers=['*'])
def dump(row):
    return {c.name:getattr(row,c.name) for c in row.__table__.columns if c.name!='password_hash'}
def commit(db):
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,'Invalid reference, duplicate value or constraint violation')
SCHEDULING_MODELS = (Assignment, Availability, Room, Section, Subject, SlotTemplate, Faculty, WorkingDay, SchedulingConstraint)
def guard_published(db,model):
    if model not in SCHEDULING_MODELS: return
    try:
        db.flush()
        for table in db.query(Timetable).filter_by(published=True):
            validate_entries(db,[dump(e) for e in db.query(Entry).filter_by(timetable_id=table.id)],complete=True)
    except (ValueError,IntegrityError) as e:
        db.rollback()
        message=str(e) if isinstance(e,ValueError) else 'a referenced record cannot be removed'
        raise HTTPException(409,'This change would invalidate a published timetable: '+message+'. Unpublish it before changing hard requirements.')
def must_get(db,model,id):
    row=db.get(model,id)
    if row is None: raise HTTPException(404,'Record not found')
    return row

class Login(BaseModel):
    email:str
    password:str
class Signup(Login):
    name:str=Field(min_length=1,max_length=100)
    password:str=Field(min_length=8,max_length=128)
@app.get('/health')
def health(): return {'status':'ok'}
@app.post('/auth/register')
def register(data:Signup,db=Depends(get_db)):
    user=User(name=data.name,email=data.email.lower().strip(),password_hash=passwords.hash(data.password),role='student')
    db.add(user); commit(db); return {'access_token':token(user),'user':dump(user)}
@app.post('/auth/login')
def login(data:Login,db=Depends(get_db)):
    user=db.query(User).filter_by(email=data.email.lower().strip()).first()
    if not user or not passwords.verify(data.password,user.password_hash): raise HTTPException(401,'Invalid email or password')
    return {'access_token':token(user),'user':dump(user)}
@app.get('/auth/me')
def me(user=Depends(current_user)): return dump(user)
class Profile(BaseModel):
    share_busy:bool
@app.patch('/auth/me')
def profile(data:Profile,user=Depends(current_user),db=Depends(get_db)):
    user.share_busy=data.share_busy; commit(db); return dump(user)
@app.get('/slots')
def slots(user=Depends(current_user),db=Depends(get_db)):
    return {'days':DAYS,'boundaries':BOUNDARIES,'slots':[dump(s) for s in db.query(SlotTemplate).order_by(SlotTemplate.day,SlotTemplate.period,SlotTemplate.system)]}

# Typed CRUD schemas and routes are generated from the explicit SQLAlchemy models.
# Unknown fields are rejected; DB checks and foreign keys are enabled in SQLite too.
def crud_routes(resource,model):
    fields={}; patches={}
    for col in model.__table__.columns:
        if col.name in ('id','password_hash'): continue
        typ=bool if isinstance(col.type,Boolean) else int if isinstance(col.type,Integer) else str
        if col.name in ('kind','system'): typ=Literal['THEORY','LAB']
        if col.name=='role': typ=Literal['admin','faculty','student']
        if col.name=='severity': typ=Literal['HARD','SOFT']
        if model==Availability and col.name=='status': typ=Literal['available','preferred','unavailable']
        if col.nullable: typ=typ|None
        default=col.default.arg if col.default and not callable(col.default.arg) else None if col.nullable else ...
        fields[col.name]=(typ,default); patches[col.name]=(typ,None)
    if model==User:
        fields['password']=(str,Field(min_length=8,max_length=128)); patches['password']=(str,Field(default=None,min_length=8,max_length=128))
    schema=create_model(f'{model.__name__}Create',__config__=ConfigDict(extra='forbid'),**fields)
    patch=create_model(f'{model.__name__}Patch',__config__=ConfigDict(extra='forbid'),**patches)
    def check(db,row):
        if model==SchedulingConstraint:
            from .configuration import check_constraint
            try: check_constraint(row)
            except ValueError as e: raise HTTPException(422,str(e))
        if model==Assignment:
            subject=must_get(db,Subject,row.subject_id)
            if subject.kind=='THEORY' and row.periods!=1: raise HTTPException(422,'Theory sessions require periods=1')
        if model==Timetable and row.published:
            try: validate_entries(db,[dump(e) for e in db.query(Entry).filter_by(timetable_id=row.id)],complete=True)
            except ValueError as e: raise HTTPException(422,str(e))
        if model==Entry:
            if must_get(db,Timetable,row.timetable_id).published: raise HTTPException(409,'Unpublish this timetable before editing')
            entries=[dump(e) for e in db.query(Entry).filter_by(timetable_id=row.timetable_id) if e.id!=row.id]
            try: validate_entries(db,entries+[dump(row)])
            except ValueError as e: raise HTTPException(422,str(e))

    def listing(db=Depends(get_db),user=Depends(admin)):
        return [dump(row) for row in db.query(model).order_by(model.id)]
    def create(data:schema,db=Depends(get_db),user=Depends(admin)):
        values=data.model_dump()
        if model==User: values['password_hash']=passwords.hash(values.pop('password'))
        row=model(**values); check(db,row); db.add(row); guard_published(db,model); commit(db); return dump(row)
    def update(id:int,data:patch,db=Depends(get_db),user=Depends(admin)):
        row=must_get(db,model,id)
        values=data.model_dump(exclude_unset=True)
        if model==User and 'password' in values: values['password_hash']=passwords.hash(values.pop('password'))
        if model==User and row.id==user.id and values.get('role',row.role)!='admin': raise HTTPException(409,'Cannot remove your own admin role')
        for k,v in values.items(): setattr(row,k,v)
        with db.no_autoflush: check(db,row)
        guard_published(db,model); commit(db); return dump(row)
    def delete(id:int,db=Depends(get_db),user=Depends(admin)):
        row=must_get(db,model,id)
        if model==User and row.id==user.id: raise HTTPException(409,'Cannot delete your own account')
        if model==Entry and must_get(db,Timetable,row.timetable_id).published: raise HTTPException(409,'Unpublish before editing')
        db.delete(row); guard_published(db,model); commit(db); return {'deleted':id}
    app.add_api_route(f'/admin/{resource}',listing,methods=['GET'],tags=['Admin CRUD'])
    app.add_api_route(f'/admin/{resource}',create,methods=['POST'],tags=['Admin CRUD'])
    app.add_api_route(f'/admin/{resource}/{{id}}',update,methods=['PATCH'],tags=['Admin CRUD'])
    app.add_api_route(f'/admin/{resource}/{{id}}',delete,methods=['DELETE'],tags=['Admin CRUD'])
for resource,model in RESOURCES.items(): crud_routes(resource,model)
class Generation(BaseModel):
    name:str=Field(min_length=1,max_length=100)
@app.post('/admin/generate')
def generation(data:Generation,user=Depends(admin),db=Depends(get_db)):
    try: return dump(generate(db,data.name))
    except SchedulingFailure as e: raise HTTPException(422,e.detail)
    except ValueError as e: raise HTTPException(422,str(e))
@app.get('/timetables')
def timetables(user=Depends(current_user),db=Depends(get_db)):
    query=db.query(Timetable)
    if user.role!='admin': query=query.filter_by(published=True)
    return [dump(t) for t in query.order_by(Timetable.id.desc())]
@app.get('/timetables/{id}')
def timetable(id:int,user=Depends(current_user),db=Depends(get_db)):
    table=must_get(db,Timetable,id)
    if not table.published and user.role!='admin': raise HTTPException(403,'Draft timetable')
    from .analytics import rows
    return dict(dump(table),entries=rows(db,id))
class SlotSelection(BaseModel):
    system:Literal['THEORY','LAB']
    codes:list[str]=Field(max_length=100)
class ImportSchedule(BaseModel):
    selections:list[SlotSelection]
@app.put('/schedule')
def import_schedule(data:ImportSchedule,user=Depends(current_user),db=Depends(get_db)):
    selected={}
    try:
        for selection in data.selections:
            for slot in map_codes(db,selection.system,selection.codes): selected[slot.id]=slot
    except ValueError as e: raise HTTPException(422,str(e))
    db.query(Registration).filter_by(user_id=user.id).delete()
    db.add_all(Registration(user_id=user.id,slot_id=id) for id in selected); commit(db)
    return [dump(s) for s in selected.values()]
@app.get('/schedule')
def schedule(user=Depends(current_user),db=Depends(get_db)):
    return {'slots':[dump(s) for s in db.query(SlotTemplate).join(Registration).filter(Registration.user_id==user.id)],'busy':{day:busy_for(db,user,day) for day in range(5)}}
@app.get('/people')
def people(q:str='',user=Depends(current_user),db=Depends(get_db)):
    return [{'id':u.id,'name':u.name,'email':u.email} for u in db.query(User).filter(User.id!=user.id,User.name.ilike(f'%{q}%')).limit(50)]
@app.get('/friends')
def friends(user=Depends(current_user),db=Depends(get_db)):
    result=[]
    for f in db.query(Friendship).filter(or_(Friendship.requester_id==user.id,Friendship.recipient_id==user.id)):
        other=db.get(User,f.recipient_id if f.requester_id==user.id else f.requester_id)
        result.append(dict(dump(f),friend={'id':other.id,'name':other.name,'share_busy':other.share_busy}))
    return result
class FriendRequest(BaseModel):
    user_id:int
@app.post('/friends')
def request_friend(data:FriendRequest,user=Depends(current_user),db=Depends(get_db)):
    must_get(db,User,data.user_id)
    if data.user_id==user.id: raise HTTPException(422,'Choose another user')
    existing=db.query(Friendship).filter(or_((Friendship.requester_id==user.id)&(Friendship.recipient_id==data.user_id),(Friendship.requester_id==data.user_id)&(Friendship.recipient_id==user.id))).first()
    if existing: raise HTTPException(409,'Friendship already exists')
    f=Friendship(requester_id=user.id,recipient_id=data.user_id); db.add(f); commit(db); return dump(f)
@app.post('/friends/{id}/accept')
def accept_friend(id:int,user=Depends(current_user),db=Depends(get_db)):
    f=must_get(db,Friendship,id)
    if f.recipient_id!=user.id: raise HTTPException(403,'Only recipient can accept')
    f.status='accepted'; commit(db); return dump(f)
@app.delete('/friends/{id}')
def remove_friend(id:int,user=Depends(current_user),db=Depends(get_db)):
    f=must_get(db,Friendship,id)
    if user.id not in (f.requester_id,f.recipient_id): raise HTTPException(403,'Not your friendship')
    db.delete(f); commit(db); return {'deleted':id}
class Window(BaseModel):
    day:int=Field(ge=0,le=4)
    start:int=Field(ge=0,le=1439)
    end:int=Field(ge=1,le=1440)
class FreeQuery(Window):
    user_ids:list[int]=Field(default=[],max_length=30)
    minimum:int=Field(default=30,ge=1,le=1440)
@app.post('/common-free')
def free(data:FreeQuery,user=Depends(current_user),db=Depends(get_db)):
    if data.start>=data.end: raise HTTPException(422,'End must follow start')
    try: users=shared_users(db,user,data.user_ids)
    except ValueError as e: raise HTTPException(403,str(e))
    return common_free([busy_for(db,u,data.day) for u in users],data.start,data.end,data.minimum)
class EventInput(Window):
    title:str=Field(min_length=1,max_length=100)
@app.get('/events')
def events(user=Depends(current_user),db=Depends(get_db)):
    return [dump(e) for e in db.query(PersonalEvent).filter_by(user_id=user.id)]
@app.post('/events')
def create_event(data:EventInput,user=Depends(current_user),db=Depends(get_db)):
    if data.start>=data.end: raise HTTPException(422,'End must follow start')
    e=PersonalEvent(user_id=user.id,**data.model_dump()); db.add(e); commit(db); return dump(e)
@app.patch('/events/{id}')
def edit_event(id:int,data:EventInput,user=Depends(current_user),db=Depends(get_db)):
    e=must_get(db,PersonalEvent,id)
    if e.user_id!=user.id: raise HTTPException(403,'Not your event')
    if data.start>=data.end: raise HTTPException(422,'End must follow start')
    for k,v in data.model_dump().items(): setattr(e,k,v)
    commit(db); return dump(e)
@app.delete('/events/{id}')
def remove_event(id:int,user=Depends(current_user),db=Depends(get_db)):
    e=must_get(db,PersonalEvent,id)
    if e.user_id!=user.id: raise HTTPException(403,'Not your event')
    db.delete(e); commit(db); return {'deleted':id}
class MeetupInput(EventInput):
    user_ids:list[int]=Field(default=[],max_length=30)
@app.get('/meetups')
def meetups(user=Depends(current_user),db=Depends(get_db)):
    return [dict(dump(m),members=[x.user_id for x in db.query(MeetupMember).filter_by(meetup_id=m.id)]) for m in db.query(Meetup).join(MeetupMember).filter(MeetupMember.user_id==user.id)]
@app.post('/meetups')
def create_meetup(data:MeetupInput,user=Depends(current_user),db=Depends(get_db)):
    if data.start>=data.end: raise HTTPException(422,'End must follow start')
    try: users=shared_users(db,user,data.user_ids)
    except ValueError as e: raise HTTPException(403,str(e))
    if any(a<data.end and b>data.start for u in users for a,b in busy_for(db,u,data.day)):
        raise HTTPException(409,'Someone is busy during this meetup')
    m=Meetup(creator_id=user.id,**data.model_dump(exclude={'user_ids'})); db.add(m); db.flush()
    db.add_all(MeetupMember(meetup_id=m.id,user_id=u.id) for u in users); commit(db); return dump(m)
@app.delete('/meetups/{id}')
def cancel_meetup(id:int,user=Depends(current_user),db=Depends(get_db)):
    m=must_get(db,Meetup,id)
    if m.creator_id!=user.id: raise HTTPException(403,'Only creator can cancel')
    db.delete(m); commit(db); return {'deleted':id}
@app.get('/faculty/availability')
def faculty_availability(user=Depends(current_user),db=Depends(get_db)):
    faculty=db.query(Faculty).filter_by(user_id=user.id).first()
    if not faculty: raise HTTPException(403,'No linked faculty profile')
    return [dump(a) for a in db.query(Availability).filter_by(faculty_id=faculty.id)]
class AvailabilityWindow(Window):
    status:Literal['available','preferred','unavailable']='available'
class AvailabilityInput(BaseModel):
    windows:list[AvailabilityWindow]=Field(max_length=50)
@app.put('/faculty/availability')
def set_availability(data:AvailabilityInput,user=Depends(current_user),db=Depends(get_db)):
    faculty=db.query(Faculty).filter_by(user_id=user.id).first()
    if not faculty: raise HTTPException(403,'No linked faculty profile')
    if any(w.start>=w.end for w in data.windows): raise HTTPException(422,'End must follow start')
    db.query(Availability).filter_by(faculty_id=faculty.id).delete()
    db.add_all(Availability(faculty_id=faculty.id,**w.model_dump()) for w in data.windows); guard_published(db,Availability); commit(db)
    return {'saved':len(data.windows)}

from .advanced import router as advanced_router
app.include_router(advanced_router)
