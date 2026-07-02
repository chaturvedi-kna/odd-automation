import bcrypt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        # Primary (bcrypt direct)
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except:
        # Fallback (passlib for legacy)
        return pwd_context.verify(plain, hashed)