from sqlalchemy import or_
from .models import User, Registration, SlotTemplate, PersonalEvent, Meetup, MeetupMember, Timetable, Entry, Assignment, Friendship

def merge(intervals):
    out=[]
    for start,end in sorted(intervals):
        if out and start<=out[-1][1]: out[-1]=(out[-1][0],max(end,out[-1][1]))
        else: out.append((start,end))
    return out

def common_free(busy_lists,start,end,minimum):
    """Complement of the union is the intersection of everyone's free time."""
    busy=merge([(max(start,a),min(end,b)) for intervals in busy_lists for a,b in intervals if a<end and b>start])
    result=[]; cursor=start
    for a,b in busy:
        if a-cursor>=minimum: result.append({'start':cursor,'end':a,'duration':a-cursor})
        cursor=max(cursor,b)
    if end-cursor>=minimum: result.append({'start':cursor,'end':end,'duration':end-cursor})
    return result

def busy_for(db,user,day):
    intervals=[]
    for slot in db.query(SlotTemplate).join(Registration,Registration.slot_id==SlotTemplate.id).filter(Registration.user_id==user.id,SlotTemplate.day==day):
        intervals.append((slot.start,slot.end))
    for e in db.query(PersonalEvent).filter_by(user_id=user.id,day=day): intervals.append((e.start,e.end))
    for m in db.query(Meetup).join(MeetupMember).filter(MeetupMember.user_id==user.id,Meetup.day==day): intervals.append((m.start,m.end))
    # Latest published timetable is the active semester schedule; drafts do not apply.
    timetable=db.query(Timetable).filter_by(published=True).order_by(Timetable.id.desc()).first()
    if timetable and user.section_id:
        for e in db.query(Entry).join(Assignment).filter(Entry.timetable_id==timetable.id,Assignment.section_id==user.section_id,Entry.day==day): intervals.append((e.start,e.end))
    return merge(intervals)

def accepted(db,left,right):
    return db.query(Friendship).filter(Friendship.status=='accepted',or_((Friendship.requester_id==left)&(Friendship.recipient_id==right),(Friendship.requester_id==right)&(Friendship.recipient_id==left))).first() is not None

def shared_users(db,user,ids):
    result=[user]
    for uid in set(ids)-{user.id}:
        other=db.get(User,uid)
        if not other or not accepted(db,user.id,uid) or not other.share_busy:
            raise ValueError('Select accepted friends who share free/busy availability')
        result.append(other)
    return result
