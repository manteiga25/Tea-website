from decimal import Decimal

from pydantic import BaseModel, ConfigDict

# The pages and the JSON routes hand out these models, not live ORM rows, so a
# template can never trigger a lazy load after its session has been closed.
# from_attributes lets model_validate() read a SQLAlchemy row directly.
class Tea(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    is_tea: bool
    has_caffeine: bool
    url: str
    img_url: str
    price: Decimal
    warning: str | None
    cook: str
    benefit_headline: str | None = None

class Herb(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    family_name: str | None
    part_used: str
    image_url: str
    benefits: list[str] = []

class Faq(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str

class Category(BaseModel):
    """A browsable grouping of teas, derived from the Benefit table."""
    name: str
    slug: str
    tea_count: int
    image_url: str | None = None
    blurb: str | None = None
