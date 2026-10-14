import os, secrets
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .db import get_db
from .models import User
SECRET=os.getenv('JWT_SECRET') or secrets.token_hex(32)
passwords=PasswordHash.recommended()
bearer=HTTPBearer(auto_error=False)
def token(user):
    return jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(hours=8)}, SECRET, algorithm='HS256')
def current_user(credentials: HTTPAuthorizationCredentials=Depends(bearer), db=Depends(get_db)):
    try:
        payload=jwt.decode(credentials.credentials, SECRET, algorithms=['HS256'])
        user=db.get(User,int(payload['sub']))
        if not user: raise ValueError()
        return user
    except (AttributeError, ValueError, KeyError, jwt.InvalidTokenError):
        raise HTTPException(401,'Sign in required')
def admin(user=Depends(current_user)):
    if user.role!='admin': raise HTTPException(403,'Administrator role required')
    return user
