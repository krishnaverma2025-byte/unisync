from app.social import common_free,busy_for
from app.models import User,Meetup,MeetupMember

def test_common_free_merges_staggered_and_overlapping_busy_intervals():
    # Theory 9–9:50, lab 8:51–9:40. Combined busy 8:51–9:50.
    assert common_free([[(540,590)],[(531,580)]],480,660,30)==[
        {'start':480,'end':531,'duration':51},{'start':590,'end':660,'duration':70}]
    assert common_free([[(480,530)],[(530,580)]],480,600,20)==[{'start':580,'end':600,'duration':20}]
    assert common_free([[(470,700)]],480,660,30)==[]
    assert common_free([[]],480,660,180)==[{'start':480,'end':660,'duration':180}]

def test_events_and_meetups_are_busy(db):
    user=db.query(User).filter_by(email='aanya@unisync.local').one()
    assert (960,990) in busy_for(db,user,0)
    meetup=Meetup(creator_id=user.id,title='Meet',day=0,start=1000,end=1040)
    db.add(meetup);db.flush();db.add(MeetupMember(meetup_id=meetup.id,user_id=user.id));db.commit()
    assert (1000,1040) in busy_for(db,user,0)
