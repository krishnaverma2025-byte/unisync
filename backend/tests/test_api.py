from conftest import headers

def test_jwt_and_roles(client):
    assert client.get('/schedule').status_code==401
    student=headers(client,'krishna@unisync.local')
    assert client.get('/admin/users',headers=student).status_code==403
    response=client.post('/auth/register',json={'name':'New','email':'new@local.test','password':'StrongPass123!','role':'admin'})
    assert response.status_code==200
    assert response.json()['user']['role']=='student'
    assert 'password_hash' not in client.get('/auth/me',headers=student).json()

def test_crud_and_unknown_fields(client):
    h=headers(client)
    r=client.post('/admin/departments',headers=h,json={'name':'Physics'})
    assert r.status_code==200
    id=r.json()['id']
    assert client.patch(f'/admin/departments/{id}',headers=h,json={'name':'Math'}).status_code==200
    assert client.post('/admin/departments',headers=h,json={'name':'Math'}).status_code==409
    assert client.post('/admin/rooms',headers=h,json={'name':'Bad','kind':'LAB','capacity':-1}).status_code==409
    assert client.post('/admin/departments',headers=h,json={'name':'X','untrusted':True}).status_code==422
    assert client.delete(f'/admin/departments/{id}',headers=h).status_code==200

def test_import_is_atomic_and_maps_all_occurrences(client):
    h=headers(client,'krishna@unisync.local')
    r=client.put('/schedule',headers=h,json={'selections':[{'system':'THEORY','codes':['A1']},{'system':'LAB','codes':['L2']}]})
    assert r.status_code==200 and len(r.json())==3
    assert client.put('/schedule',headers=h,json={'selections':[{'system':'LAB','codes':['A1']}]}).status_code==422
    assert len(client.get('/schedule',headers=h).json()['slots'])==3

def test_friend_consent_and_meetup(client):
    krishna=headers(client,'krishna@unisync.local');aanya=headers(client,'aanya@unisync.local')
    payload={'user_ids':[3], 'day':0,'start':800,'end':840,'minimum':30}
    assert client.post('/common-free',headers=krishna,json=payload).json()==[{'start':800,'end':840,'duration':40}]
    assert client.patch('/auth/me',headers=aanya,json={'share_busy':False}).status_code==200
    assert client.post('/common-free',headers=krishna,json=payload).status_code==403
    client.patch('/auth/me',headers=aanya,json={'share_busy':True})
    meetup={k:v for k,v in payload.items() if k!='minimum'}|{'title':'Lunch together'}
    r=client.post('/meetups',headers=krishna,json=meetup)
    assert r.status_code==200
    assert len(client.get('/meetups',headers=aanya).json())==1
    assert client.post('/meetups',headers=krishna,json=meetup).status_code==409
    assert client.delete(f"/meetups/{r.json()['id']}",headers=aanya).status_code==403
    assert client.post('/common-free',headers=krishna,json=payload).json()==[]
    assert client.delete(f"/meetups/{r.json()['id']}",headers=krishna).status_code==200

def test_generate_publish_and_constraint_lock(client):
    h=headers(client)
    r=client.post('/admin/generate',headers=h,json={'name':'Semester demo'})
    assert r.status_code==200
    id=r.json()['id']
    assert client.patch(f'/admin/timetables/{id}',headers=h,json={'published':True}).status_code==200
    student=headers(client,'krishna@unisync.local')
    table=client.get(f'/timetables/{id}',headers=student).json()
    assert len(table['entries'])==14
    assert client.patch('/admin/rooms/1',headers=h,json={'capacity':1}).status_code==409
    first=table['entries'][0]
    assert client.delete(f"/admin/entries/{first['id']}",headers=h).status_code==409
    assert client.delete(f'/admin/timetables/{id}',headers=h).status_code==200
    assert client.patch('/admin/rooms/1',headers=h,json={'capacity':50}).status_code==200

def test_pending_friend_needs_recipient_acceptance(client):
    aanya=headers(client,'aanya@unisync.local');rohan=headers(client,'rohan@unisync.local')
    r=client.post('/friends',headers=aanya,json={'user_id':4}); assert r.status_code==200
    id=r.json()['id']
    payload={'day':1,'start':800,'end':840,'user_ids':[4],'minimum':30}
    assert client.post('/common-free',headers=aanya,json=payload).status_code==403
    assert client.post(f'/friends/{id}/accept',headers=aanya).status_code==403
    assert client.post(f'/friends/{id}/accept',headers=rohan).status_code==200
    assert client.post('/common-free',headers=aanya,json=payload).status_code==200
