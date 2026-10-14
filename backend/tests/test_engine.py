from collections import Counter
import pytest
from app.engine import generate,candidates,validate_entries,overlaps,SchedulingFailure
from app.models import Assignment,Entry,Availability,Room,Subject
from app.main import dump

def test_generated_schedule_has_no_clock_clashes_and_exact_counts(db):
    timetable=generate(db,'Test')
    entries=[dump(e) for e in db.query(Entry).filter_by(timetable_id=timetable.id)]
    enriched=validate_entries(db,entries,complete=True)
    assert len(entries)==14
    counts=Counter(e['assignment_id'] for e in entries)
    for a in db.query(Assignment): assert counts[a.id]==a.weekly_sessions
    for i,left in enumerate(enriched):
        for right in enriched[i+1:]:
            if overlaps(left,right): assert all(left[k]!=right[k] for k in ('faculty_id','section_id','room_id'))
    for entry in entries:
        assert not(entry['start']<840 and entry['end']>800)
        assignment=db.get(Assignment,entry['assignment_id'])
        room=db.get(Room,entry['room_id'])
        assert room.kind==db.get(Subject,assignment.subject_id).kind
        if room.kind=='LAB': assert len(entry['codes'].split(','))==2

def test_missing_availability_is_infeasible(db):
    db.query(Availability).delete(); db.commit()
    with pytest.raises(SchedulingFailure) as error: generate(db,'Impossible')
    assert error.value.detail['status']=='INFEASIBLE'
    assert error.value.detail['issues']
    assert error.value.detail['suggestions']
    assert db.query(Entry).count()==0

def test_lab_blocks_never_cross_lunch(db):
    assignment=db.query(Assignment).filter_by(periods=2).first()
    options=candidates(db,assignment)
    assert options
    assert all(not(o['start']<840 and o['end']>800) for o in options)
    assert all(len(o['codes'].split(','))==2 for o in options)

def test_staggered_theory_lab_overlap_detected(db):
    theory=db.query(Assignment).filter_by(subject_id=1,section_id=1).first()
    lab=db.query(Assignment).filter_by(subject_id=3,section_id=1).first()
    left=next(c for c in candidates(db,theory) if c['day']==0 and c['start']==540)
    right=next(c for c in candidates(db,lab) if c['day']==0 and c['start']==531)
    with pytest.raises(ValueError,match='clash'): validate_entries(db,[left,right])

def test_wrong_room_capacity_or_type_rejected(db):
    a=db.query(Assignment).first()
    db.query(Room).filter_by(kind='THEORY').update({'capacity':1});db.commit()
    assert not candidates(db,a)
