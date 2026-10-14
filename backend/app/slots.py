"""Transcribed from docs/slot-template.png. Minutes after midnight, half-open intervals.
The unlabelled theory cell above L6 has no theory period. 18:51–19:00 is
shown as a theory break with no theory code; L36 uses LAB 18:31–19:20.
"""
from .models import SlotTemplate
DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday']
THEORY_TIMES = [(480,530),(540,590),(600,650),(660,710),(720,770),None,(840,890),(900,950),(960,1010),(1020,1070),(1080,1130),None,(1141,1190)]
LAB_TIMES = [(480,530),(531,580),(591,640),(641,690),(700,750),(751,800),(840,890),(891,940),(951,1000),(1001,1050),(1060,1110),(1111,1160)]
GRID = [
 ['A1','F1','D1','TB1','TG1',None,'A2','F2','D2','TB2','TG2',None,'V3'],
 ['B1','G1','E1','TC1','TAA1',None,'B2','G2','E2','TC2','TAA2',None,'V4'],
 ['C1','A1','F1','V1','V2',None,'C2','A2','F2','TD2','TBB2',None,'V5'],
 ['D1','B1','G1','TE1','TCC1',None,'D2','B2','G2','TE2','TCC2',None,'V6'],
 ['E1','C1','TA1','TF1','TD1',None,'E2','C2','TA2','TF2','TDD2',None,'V7'],
]
BOUNDARIES = {'lunch': {'start':800,'end':840}, 'theory_evening_break':{'start':1131,'end':1140}, 'note':'Blank theory column has no slot; no lab slot under V3–V7.'}
def template_rows():
    rows=[]
    for day, codes in enumerate(GRID):
        for period, theory in enumerate(codes):
            lab = f'L{day*6+period+1}' if period<6 else f'L{31+day*6+period-6}' if period<12 else None
            label = f'{theory}/{lab}' if theory and lab else theory or lab
            if theory:
                start,end=THEORY_TIMES[period]
                rows.append(dict(day=day,system='THEORY',code=theory,label=label,period=period+1,block='AM' if period<6 else 'PM',start=start,end=end))
            if lab:
                start,end=LAB_TIMES[period]
                rows.append(dict(day=day,system='LAB',code=lab,label=label,period=period+1,block='AM' if period<6 else 'PM',start=start,end=end))
    return rows
def seed_slots(db):
    db.add_all(SlotTemplate(**row) for row in template_rows())
def map_codes(db, system, codes):
    codes=set(codes)
    slots=db.query(SlotTemplate).filter(SlotTemplate.system==system, SlotTemplate.code.in_(codes)).all()
    missing=codes-{s.code for s in slots}
    if missing:
        raise ValueError(f'Unknown {system} slot codes: {", ".join(sorted(missing))}')
    return slots
