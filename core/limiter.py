import os
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("LIMITER_ENABLED", "true").lower() != "false"
)
