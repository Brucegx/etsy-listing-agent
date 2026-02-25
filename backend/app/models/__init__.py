from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models so that Base.metadata.create_all picks them up.
from app.models.user import User  # noqa: E402, F401
from app.models.job import Job  # noqa: E402, F401
from app.models.api_key import ApiKey  # noqa: E402, F401
