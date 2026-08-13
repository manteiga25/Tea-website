import re

from flask import g, current_app
from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import selectinload, sessionmaker

from database import Models, Tables
from database.Tables import ingredients, tea_benefit

app = current_app.app_context()

DATABASE = app.app.config['DATABASE_URL']

# One engine for the whole process — it owns the connection pool. Sessions are
# cheap and created per request below.
engine = create_engine(f"sqlite:///{DATABASE}")
SessionFactory = sessionmaker(bind=engine)

# The Benefit table was scraped from several places, so a few concepts arrived
# under two spellings. Everything the front-end shows goes through this map so
# the user never sees "Sleep" and "Sleep Support" as two separate categories.
BENEFIT_ALIASES = {
    "Digestive": "Digestion",
    "Sleep Support": "Sleep",
    "Stress": "Stress Relief",
    "Good Mood": "Mood Support",
    "Respiratory Health": "Respiratory",
    "Throat Healthy": "Throat Health",
    "Women’s Cycle": "Women's Cycle",
}

CATEGORY_BLURBS = {
    "Digestion": "Soothing blends for a settled stomach, after meals or any time of day.",
    "Relaxation": "Slow down with gentle botanicals made for winding down.",
    "Sleep": "Evening rituals that help you drift off naturally.",
    "Stress Relief": "Adaptogens and calming nervines to build everyday resilience.",
    "Seasonal Care": "Warming support for when the weather turns.",
    "Immunity": "Elderflower, echinacea and friends for your daily defences.",
    "Energy": "A clean lift, with or without caffeine.",
    "Detox": "Dandelion, nettle and burdock to support your natural cleansing.",
    "Women's Health": "Blends traditionally used to support the cycle and beyond.",
    "Pre & Postnatal": "Carefully chosen herbs for pregnancy, birth and nursing.",
    "Heart Health": "Hawthorn and hibiscus for a cup that looks after you.",
    "Respiratory": "Open up and breathe easy with eucalyptus and friends.",
    "Throat Health": "Slippery elm and licorice to coat and comfort.",
    "Mood Support": "Bright, floral cups crafted to lift the spirits.",
    "Joint Health": "Nettle and turmeric for everyday mobility.",
    "Nausea": "Ginger-forward blends for queasy moments.",
    "Laxative": "Senna-based teas for occasional constipation.",
    "Skin Health": "Botanicals traditionally used for a healthy glow.",
    "Water Retention": "Gently diuretic herbs to help you feel less puffy.",
}


def __get_session():
    """One session per request, closed by the teardown handler below."""
    session = getattr(g, '_session', None)
    if session is None:
        session = g._session = SessionFactory()
    return session

def getProductByIds(id: list[int]):
    rows = __get_session().scalars(
        select(Tables.Tea).where(Tables.Tea.id.in_(id))
    ).all()

    return [Models.Tea.model_validate(row) for row in rows]

def getProductById(id: int):
    return Models.Tea.model_validate(__get_session().get(Tables.Tea, id))


# --------------------------------------------------------------------------
# Helpers used by the rendered pages
# --------------------------------------------------------------------------

def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

def canonicalBenefit(name: str) -> str:
    return BENEFIT_ALIASES.get(name, name)

def getProductByIdOrNone(id: int):
    row = __get_session().get(Tables.Tea, id)
    return Models.Tea.model_validate(row) if row else None

def getAllProducts():
    rows = __get_session().scalars(
        select(Tables.Tea).order_by(Tables.Tea.name)
    ).all()
    return [Models.Tea.model_validate(row) for row in rows]

def countProducts() -> int:
    return __get_session().scalar(select(func.count()).select_from(Tables.Tea))

def countHerbs() -> int:
    return __get_session().scalar(select(func.count()).select_from(Tables.Herb))

def getBenefitsByTea(tea_ids: list[int]) -> dict[int, list[str]]:
    """Canonical benefit names for each tea id, so cards can show their tags."""
    if not tea_ids:
        return {}

    rows = __get_session().execute(
        select(tea_benefit.c.tea, Tables.Benefit.benefit)
        .join(Tables.Benefit, Tables.Benefit.id == tea_benefit.c.benefit)
        .where(tea_benefit.c.tea.in_(tea_ids))
        .order_by(Tables.Benefit.benefit)
    ).all()

    grouped: dict[int, list[str]] = {tea_id: [] for tea_id in tea_ids}
    for tea_id, benefit in rows:
        canonical = canonicalBenefit(benefit)
        if canonical not in grouped[tea_id]:
            grouped[tea_id].append(canonical)
    return grouped

def getBenefitsForTea(tea_id: int) -> list[str]:
    return getBenefitsByTea([tea_id]).get(tea_id, [])

def getAllBenefits() -> list[tuple[str, int]]:
    """Every benefit that is actually attached to a tea, with its tea count."""
    rows = __get_session().execute(
        select(Tables.Benefit.benefit, tea_benefit.c.tea)
        .join(tea_benefit, tea_benefit.c.benefit == Tables.Benefit.id)
    ).all()

    # Counted over canonical names, since two aliases may cover the same tea.
    counts: dict[str, set] = {}
    for benefit, tea_id in rows:
        counts.setdefault(canonicalBenefit(benefit), set()).add(tea_id)

    return sorted(
        ((name, len(teas)) for name, teas in counts.items()),
        key=lambda pair: (-pair[1], pair[0]),
    )

def __benefitIdsFor(names: list[str]) -> list[int]:
    """Every Benefit row id matching the given canonical names (aliases included)."""
    if not names:
        return []

    wanted = {canonicalBenefit(name) for name in names}
    rows = __get_session().execute(
        select(Tables.Benefit.id, Tables.Benefit.benefit)
    ).all()
    return [row_id for row_id, benefit in rows if canonicalBenefit(benefit) in wanted]

def getCategories(limit: int = 8) -> list[Models.Category]:
    """The largest benefit groups, each illustrated by its most typical herb."""
    session = __get_session()
    categories = []

    for name, count in getAllBenefits()[:limit]:
        benefit_ids = __benefitIdsFor([name])

        image_url = session.scalar(
            select(Tables.Herb.image_url)
            .join(ingredients, ingredients.c.herb == Tables.Herb.name)
            .join(tea_benefit, tea_benefit.c.tea == ingredients.c.tea)
            .where(tea_benefit.c.benefit.in_(benefit_ids))
            .group_by(Tables.Herb.id)
            .order_by(func.count().desc(), Tables.Herb.name)
            .limit(1)
        )

        categories.append(Models.Category(
            name=name,
            slug=slugify(name),
            tea_count=count,
            image_url=image_url,
            blurb=CATEGORY_BLURBS.get(name),
        ))
    return categories

def getIngredients(tea_id: int) -> list[Models.Herb]:
    """The herbs in a tea, each carrying the benefits shown in the hover card."""
    tea = __get_session().get(
        Tables.Tea, tea_id,
        options=[selectinload(Tables.Tea.herbs).selectinload(Tables.Herb.benefits)],
    )
    if tea is None:
        return []

    return [
        Models.Herb(
            id=herb.id,
            name=herb.name,
            description=herb.description,
            family_name=herb.family_name,
            part_used=herb.part_used,
            image_url=herb.image_url,
            benefits=sorted({canonicalBenefit(b.benefit) for b in herb.benefits}),
        )
        for herb in tea.herbs
    ]

def getAllHerbNames() -> list[str]:
    return list(__get_session().scalars(
        select(Tables.Herb.name)
        .where(Tables.Herb.name.in_(select(ingredients.c.herb)))
        .order_by(Tables.Herb.name)
    ).all())

def getFaqs(tea_id: int) -> list[Models.Faq]:
    rows = __get_session().scalars(
        select(Tables.Faq).where(Tables.Faq.tea == tea_id).order_by(Tables.Faq.id)
    ).all()
    return [Models.Faq.model_validate(row) for row in rows]

def searchProducts(
    query: str | None = None,
    benefits: list[str] | None = None,
    herbs: list[str] | None = None,
    is_tea: bool | None = None,
    has_caffeine: bool | None = None,
    semantic_ids: list[int] | None = None,
    sort: str = "relevance",
) -> list[Models.Tea]:
    """Filtered catalogue search.

    Facets combine with AND; values inside one facet combine with OR. When a
    text query is given, semantic_ids (from the FAISS name index) widen the
    plain LIKE match so "sleepy" still finds Nighty Night.
    """
    statement = select(Tables.Tea)

    if query:
        like = f"%{query.strip()}%"
        matches = [
            Tables.Tea.name.like(like),
            Tables.Tea.description.like(like),
            Tables.Tea.benefit_headline.like(like),
        ]
        if semantic_ids:
            matches.append(Tables.Tea.id.in_(semantic_ids))
        statement = statement.where(or_(*matches))

    if benefits:
        benefit_ids = __benefitIdsFor(benefits)
        if not benefit_ids:
            return []
        statement = statement.where(Tables.Tea.id.in_(
            select(tea_benefit.c.tea).where(tea_benefit.c.benefit.in_(benefit_ids))
        ))

    if herbs:
        statement = statement.where(Tables.Tea.id.in_(
            select(ingredients.c.tea).where(ingredients.c.herb.in_(herbs))
        ))

    if is_tea is not None:
        statement = statement.where(Tables.Tea.is_tea == is_tea)

    if has_caffeine is not None:
        statement = statement.where(Tables.Tea.has_caffeine == has_caffeine)

    rows = __get_session().scalars(statement.order_by(Tables.Tea.name)).all()
    teas = [Models.Tea.model_validate(row) for row in rows]

    if sort == "name":
        return teas
    if sort == "name_desc":
        return list(reversed(teas))

    # Relevance: whatever the embedder ranked highest floats to the top.
    rank = {tea_id: i for i, tea_id in enumerate(semantic_ids or [])}
    return sorted(teas, key=lambda tea: (rank.get(tea.id, len(rank)), tea.name))

@current_app.teardown_appcontext
def close_connection(exception):
    session = getattr(g, '_session', None)
    if session is not None:
        session.close()
