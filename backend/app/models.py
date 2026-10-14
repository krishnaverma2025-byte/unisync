from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from .db import Base
class Department(Base):
    __tablename__ = 'departments'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
class Semester(Base):
    __tablename__ = 'semesters'
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    number = Column(Integer, nullable=False)
    academic_year = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint('course_id','number','academic_year'), CheckConstraint('number >= 1 AND number <= 12'))
class WorkingDay(Base):
    __tablename__ = 'working_days'
    id = Column(Integer, primary_key=True)
    day = Column(Integer, nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint('day >= 0 AND day <= 4'),)
class Section(Base):
    __tablename__ = 'sections'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    size = Column(Integer, nullable=False)
    semester_id = Column(Integer, ForeignKey('semesters.id'))
    __table_args__ = (CheckConstraint('size > 0'),)
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default='student')
    section_id = Column(Integer, ForeignKey('sections.id'))
    share_busy = Column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("role IN ('admin','faculty','student')"),)
class Faculty(Base):
    __tablename__ = 'faculty'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    max_classes_day = Column(Integer, nullable=False, default=6)
    max_classes_week = Column(Integer, nullable=False, default=24)
    __table_args__ = (CheckConstraint('max_classes_day > 0 AND max_classes_week > 0'),)
class Subject(Base):
    __tablename__ = 'subjects'
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    kind = Column(String, nullable=False)
    credits = Column(Integer, nullable=False, default=3)
    difficulty = Column(Integer, nullable=False, default=3)
    __table_args__ = (CheckConstraint("kind IN ('THEORY','LAB')"), CheckConstraint('credits >= 0 AND difficulty >= 1 AND difficulty <= 5'))
class Room(Base):
    __tablename__ = 'rooms'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    kind = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    __table_args__ = (CheckConstraint("kind IN ('THEORY','LAB')"), CheckConstraint('capacity > 0'))
class SlotTemplate(Base):
    __tablename__ = 'slots'
    id = Column(Integer, primary_key=True)
    day = Column(Integer, nullable=False)
    system = Column(String, nullable=False)
    code = Column(String, nullable=False)
    label = Column(String, nullable=False)
    period = Column(Integer, nullable=False)
    block = Column(String, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('day','system','code'), CheckConstraint('day >= 0 AND day <= 4'), CheckConstraint('start >= 0 AND end <= 1440 AND end > start'), CheckConstraint("system IN ('THEORY','LAB')"))
class Availability(Base):
    __tablename__ = 'availability'
    id = Column(Integer, primary_key=True)
    faculty_id = Column(Integer, ForeignKey('faculty.id'), nullable=False)
    status = Column(String, nullable=False, default='available')
    day = Column(Integer, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    __table_args__ = (CheckConstraint('day >= 0 AND day <= 4'), CheckConstraint('start >= 0 AND end <= 1440 AND end > start'))
class SchedulingConstraint(Base):
    __tablename__ = 'constraints'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    severity = Column(String, nullable=False, default='SOFT')
    rule = Column(String, nullable=False)
    faculty_id = Column(Integer, ForeignKey('faculty.id'))
    subject_id = Column(Integer, ForeignKey('subjects.id'))
    section_id = Column(Integer, ForeignKey('sections.id'))
    value = Column(Integer, nullable=False, default=0)
    weight = Column(Integer, nullable=False, default=100)
    enabled = Column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("severity IN ('HARD','SOFT')"), CheckConstraint('weight >= 0 AND weight <= 1000'))
class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True)
    faculty_id = Column(Integer, ForeignKey('faculty.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    section_id = Column(Integer, ForeignKey('sections.id'), nullable=False)
    weekly_sessions = Column(Integer, nullable=False, default=3)
    periods = Column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint('weekly_sessions > 0 AND weekly_sessions <= 10'), CheckConstraint('periods >= 1 AND periods <= 6'))
class Timetable(Base):
    __tablename__ = 'timetables'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    published = Column(Boolean, nullable=False, default=False)
    solver_status = Column(String, nullable=False, default='MANUAL')
class Entry(Base):
    __tablename__ = 'entries'
    id = Column(Integer, primary_key=True)
    timetable_id = Column(Integer, ForeignKey('timetables.id', ondelete='CASCADE'), nullable=False)
    assignment_id = Column(Integer, ForeignKey('assignments.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    day = Column(Integer, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    codes = Column(String, nullable=False)
class Registration(Base):
    __tablename__ = 'registrations'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    slot_id = Column(Integer, ForeignKey('slots.id'), nullable=False)
    __table_args__ = (UniqueConstraint('user_id','slot_id'),)
class Friendship(Base):
    __tablename__ = 'friendships'
    id = Column(Integer, primary_key=True)
    requester_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    recipient_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    status = Column(String, nullable=False, default='pending')
    __table_args__ = (UniqueConstraint('requester_id','recipient_id'), CheckConstraint('requester_id != recipient_id'))
class PersonalEvent(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String, nullable=False)
    day = Column(Integer, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    __table_args__ = (CheckConstraint('day >= 0 AND day <= 4'), CheckConstraint('start >= 0 AND end <= 1440 AND end > start'))
class Meetup(Base):
    __tablename__ = 'meetups'
    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String, nullable=False)
    day = Column(Integer, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    __table_args__ = (CheckConstraint('day >= 0 AND day <= 4'), CheckConstraint('start >= 0 AND end <= 1440 AND end > start'))
class MeetupMember(Base):
    __tablename__ = 'meetup_members'
    id = Column(Integer, primary_key=True)
    meetup_id = Column(Integer, ForeignKey('meetups.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    __table_args__ = (UniqueConstraint('meetup_id','user_id'),)
class ChangeRequest(Base):
    __tablename__ = 'change_requests'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    timetable_id = Column(Integer, ForeignKey('timetables.id', ondelete='CASCADE'), nullable=False)
    entry_id = Column(Integer, ForeignKey('entries.id', ondelete='CASCADE'))
    reason = Column(String, nullable=False)
    status = Column(String, nullable=False, default='pending')
    admin_note = Column(String, nullable=False, default='')
    __table_args__ = (CheckConstraint("status IN ('pending','approved','rejected')"),)
RESOURCES = {'courses':Course, 'semesters':Semester, 'working-days':WorkingDay, 'constraints':SchedulingConstraint,'departments':Department,'faculty':Faculty,'subjects':Subject,'sections':Section,'rooms':Room,'slots':SlotTemplate,'availability':Availability,'assignments':Assignment,'timetables':Timetable,'entries':Entry,'users':User}
