import pytest
from app.slots import map_codes,template_rows
from app.models import SlotTemplate

def test_grid_transcription(db):
    rows=template_rows()
    assert len(rows)==115
    assert len([s for s in rows if s['system']=='LAB'])==60
    assert {s['code'] for s in rows if s['system']=='LAB'}=={f'L{i}' for i in range(1,61)}
    assert [(s.day,s.start,s.end) for s in map_codes(db,'THEORY',['A1'])]==[(0,480,530),(2,540,590)]
    assert [(s.day,s.start,s.end) for s in map_codes(db,'THEORY',['A2'])]==[(0,840,890),(2,900,950)]
    assert [(s.day,s.start,s.end) for s in map_codes(db,'THEORY',['V7'])]==[(4,1141,1190)]
    assert map_codes(db,'LAB',['L6'])[0].end==800
    assert map_codes(db,'LAB',['L36'])[0].start==1111
    assert map_codes(db,'LAB',['L60'])[0].end==1160
    assert map_codes(db,'THEORY',['TDD2'])[0].day==4
    assert db.query(SlotTemplate).filter_by(system='THEORY',period=6).count()==0
    assert db.query(SlotTemplate).filter_by(system='THEORY',period=12).count()==0
    assert db.query(SlotTemplate).filter_by(system='LAB',period=13).count()==0

def test_distinct_systems(db):
    theory=map_codes(db,'THEORY',['F1'])[0]
    lab=map_codes(db,'LAB',['L2'])[0]
    assert theory.label==lab.label=='F1/L2'
    assert (theory.start,theory.end)==(540,590)
    assert (lab.start,lab.end)==(531,580)
    with pytest.raises(ValueError): map_codes(db,'LAB',['A1'])
    with pytest.raises(ValueError): map_codes(db,'THEORY',['A1/L1'])
