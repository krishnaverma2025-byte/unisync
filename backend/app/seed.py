"""Run explicitly; never seeds automatically on application startup."""
from .db import Base,engine,SessionLocal
from .models import *
from .slots import seed_slots,map_codes
from .auth import passwords
import os

def seed(db):
    if db.query(User).first():
        seed_v2(db); return False
    demo_password=os.environ.get('DEMO_PASSWORD')
    if not demo_password or len(demo_password)<8:
        raise ValueError('Set DEMO_PASSWORD locally to at least 8 characters before seeding.')
    d=Department(name='Computer Science'); db.add(d); db.flush()
    sections=[Section(name='CSE-A',department_id=d.id,size=30),Section(name='CSE-B',department_id=d.id,size=25)]
    db.add_all(sections); db.flush()
    users=[User(name=name,email=email,password_hash=passwords.hash(demo_password),role=role) for name,email,role in [('Coordinator','admin@unisync.local','admin'),('Krishna','krishna@unisync.local','student'),('Aanya','aanya@unisync.local','student'),('Rohan','rohan@unisync.local','student'),('Dr. Meera','meera@unisync.local','faculty')]]
    db.add_all(users); db.flush()
    faculty=[Faculty(name='Dr. Meera',department_id=d.id,user_id=users[4].id),Faculty(name='Prof. Arjun',department_id=d.id)]
    db.add_all(faculty); db.flush()
    subjects=[Subject(code='CS101',name='Data Structures',kind='THEORY',department_id=d.id),Subject(code='CS102',name='Database Systems',kind='THEORY',department_id=d.id),Subject(code='CS103L',name='Programming Lab',kind='LAB',department_id=d.id)]
    db.add_all(subjects); db.flush()
    db.add_all([Room(name='SJT 101',kind='THEORY',capacity=60),Room(name='SJT 102',kind='THEORY',capacity=40),Room(name='Programming Lab 1',kind='LAB',capacity=40)])
    seed_slots(db)
    for f in faculty:
        for day in range(5): db.add(Availability(faculty_id=f.id,day=day,start=480,end=1160))
    for section in sections:
        for index,subject in enumerate(subjects):
            db.add(Assignment(faculty_id=faculty[index%2].id,subject_id=subject.id,section_id=section.id,weekly_sessions=1 if subject.kind=='LAB' else 3,periods=2 if subject.kind=='LAB' else 1))
    db.flush()
    for user,codes,labs in [(users[1],['A1','TB1'],['L31','L32']),(users[2],['F1','C1'],['L3','L4']),(users[3],['D1','TG1'],['L49','L50'])]:
        for slot in map_codes(db,'THEORY',codes)+map_codes(db,'LAB',labs): db.add(Registration(user_id=user.id,slot_id=slot.id))
    db.add_all([Friendship(requester_id=users[1].id,recipient_id=users[2].id,status='accepted'),Friendship(requester_id=users[1].id,recipient_id=users[3].id,status='accepted')])
    db.add(PersonalEvent(user_id=users[2].id,title='Study group',day=0,start=960,end=990))
    db.commit(); seed_v2(db); return True
def seed_v2(db):
    from .configuration import initialize, seed_preferences
    initialize(db); seed_preferences(db)
    department=db.query(Department).filter_by(name='Computer Science').first()
    if department and not db.query(Course).first():
        course=Course(name='B.Tech Computer Science',department_id=department.id);db.add(course);db.flush()
        semester=Semester(course_id=course.id,number=3,academic_year='2026–27');db.add(semester);db.flush()
        for section in db.query(Section).filter(Section.name.in_(['CSE-A','CSE-B'])):
            if section.semester_id is None: section.semester_id=semester.id
        db.commit()
if __name__=='__main__':
    from .migrations import migrate
    migrate(engine)
    with SessionLocal() as db:
        print('Demo data seeded. Use your locally configured DEMO_PASSWORD.' if seed(db) else 'Existing users retained; missing v2 demo configuration added idempotently.')
