from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
	access_token: str
	token_type: str


class TokenData(BaseModel):
	email: Optional[str] = None


class RefreshToken(BaseModel):
	refresh_token: str
	expires_at: datetime.datetime