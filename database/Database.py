import re
import sqlite3
from flask import g, current_app

from database import Models

app = current_app.app_context()

DATABASE = app.app.config['DATABASE_URL']

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


def __get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def getProductByIds(id: list[int]):
    placeholders = ", ".join("?" for _ in id)

    data_row = __get_db().execute(
        f"SELECT * FROM Tea WHERE id IN ({placeholders});", id
    ).fetchall()

    return [Models.Tea.model_validate(dict(row)) for row in data_row]

def getProductById(id: int):
    return Models.Tea.model_validate(dict(__get_db().execute(
        "SELECT * FROM Tea WHERE id == ?;", (id,)
    ).fetchone()))


# --------------------------------------------------------------------------
# Helpers used by the rendered pages
# --------------------------------------------------------------------------

def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

def canonicalBenefit(name: str) -> str:
    return BENEFIT_ALIASES.get(name, name)

def getProductByIdOrNone(id: int):
    row = __get_db().execute("SELECT * FROM Tea WHERE id == ?;", (id,)).fetchone()
    return Models.Tea.model_validate(dict(row)) if row else None

def getAllProducts():
    rows = __get_db().execute("SELECT * FROM Tea ORDER BY name;").fetchall()
    return [Models.Tea.model_validate(dict(row)) for row in rows]

def countProducts() -> int:
    return __get_db().execute("SELECT COUNT(*) AS c FROM Tea;").fetchone()["c"]

def countHerbs() -> int:
    return __get_db().execute("SELECT COUNT(*) AS c FROM Herb;").fetchone()["c"]

def getBenefitsByTea(tea_ids: list[int]) -> dict[int, list[str]]:
    """Canonical benefit names for each tea id, so cards can show their tags."""
    if not tea_ids:
        return {}

    placeholders = ", ".join("?" for _ in tea_ids)
    rows = __get_db().execute(
        f"""SELECT tb.tea AS tea, b.benefit AS benefit
            FROM Tea_benefit tb
            JOIN Benefit b ON b.id = tb.benefit
            WHERE tb.tea IN ({placeholders})
            ORDER BY b.benefit;""",
        tea_ids,
    ).fetchall()

    grouped: dict[int, list[str]] = {tea_id: [] for tea_id in tea_ids}
    for row in rows:
        benefit = canonicalBenefit(row["benefit"])
        if benefit not in grouped[row["tea"]]:
            grouped[row["tea"]].append(benefit)
    return grouped

def getBenefitsForTea(tea_id: int) -> list[str]:
    return getBenefitsByTea([tea_id]).get(tea_id, [])

def getAllBenefits() -> list[tuple[str, int]]:
    """Every benefit that is actually attached to a tea, with its tea count."""
    rows = __get_db().execute(
        """SELECT b.benefit AS benefit, tb.tea AS tea
           FROM Tea_benefit tb
           JOIN Benefit b ON b.id = tb.benefit;"""
    ).fetchall()

    # Counted over canonical names, since two aliases may cover the same tea.
    counts: dict[str, set] = {}
    for row in rows:
        counts.setdefault(canonicalBenefit(row["benefit"]), set()).add(row["tea"])

    return sorted(
        ((name, len(teas)) for name, teas in counts.items()),
        key=lambda pair: (-pair[1], pair[0]),
    )

def __benefitIdsFor(names: list[str]) -> list[int]:
    """Every Benefit row id matching the given canonical names (aliases included)."""
    if not names:
        return []

    wanted = {canonicalBenefit(name) for name in names}
    rows = __get_db().execute("SELECT id, benefit FROM Benefit;").fetchall()
    return [row["id"] for row in rows if canonicalBenefit(row["benefit"]) in wanted]

def getCategories(limit: int = 8) -> list[Models.Category]:
    """The largest benefit groups, each illustrated by its most typical herb."""
    categories = []
    for name, count in getAllBenefits()[:limit]:
        benefit_ids = __benefitIdsFor([name])
        placeholders = ", ".join("?" for _ in benefit_ids)
        row = __get_db().execute(
            f"""SELECT h.image_url AS image_url, COUNT(*) AS c
                FROM Tea_benefit tb
                JOIN Ingredients i ON i.tea = tb.tea
                JOIN Herb h ON h.name = i.herb
                WHERE tb.benefit IN ({placeholders})
                GROUP BY h.id
                ORDER BY c DESC, h.name
                LIMIT 1;""",
            benefit_ids,
        ).fetchone()

        categories.append(Models.Category(
            name=name,
            slug=slugify(name),
            tea_count=count,
            image_url=row["image_url"] if row else None,
            blurb=CATEGORY_BLURBS.get(name),
        ))
    return categories

def getIngredients(tea_id: int) -> list[Models.Herb]:
    """The herbs in a tea, each carrying the benefits shown in the hover card."""
    rows = __get_db().execute(
        """SELECT h.*
           FROM Ingredients i
           JOIN Herb h ON h.name = i.herb
           WHERE i.tea = ?
           ORDER BY i.id;""",
        (tea_id,),
    ).fetchall()

    herbs = []
    for row in rows:
        benefits = __get_db().execute(
            """SELECT b.benefit AS benefit
               FROM Herb_benefit hb
               JOIN Benefit b ON b.id = hb.benefit
               WHERE hb.herb = ?
               ORDER BY b.benefit;""",
            (row["id"],),
        ).fetchall()

        herb = dict(row)
        herb["benefits"] = sorted({canonicalBenefit(b["benefit"]) for b in benefits})
        herbs.append(Models.Herb.model_validate(herb))
    return herbs

def getAllHerbNames() -> list[str]:
    rows = __get_db().execute(
        """SELECT DISTINCT h.name AS name
           FROM Ingredients i
           JOIN Herb h ON h.name = i.herb
           ORDER BY h.name;"""
    ).fetchall()
    return [row["name"] for row in rows]

def getFaqs(tea_id: int) -> list[Models.Faq]:
    rows = __get_db().execute(
        "SELECT id, question, answer FROM Faq WHERE tea = ? ORDER BY id;", (tea_id,)
    ).fetchall()
    return [Models.Faq.model_validate(dict(row)) for row in rows]

def searchProducts(
    query: str | None = None,
    benefits: list[str] | None = None,
    herbs: list[str] | None = None,
    is_tea: bool | None = None,
    has_caffeine: bool | None = None,
    semantic_ids: list[int] | None = None,
    sort: str = "relevance",
) -> list[Models.Tea]:
    """Filtered catalogue search."""
    clauses = []
    params: list = []

    if query:
        like = f"%{query.strip()}%"
        text_clause = "(t.name LIKE ? OR t.description LIKE ? OR t.benefit_headline LIKE ?)"
        params += [like, like, like]
        if semantic_ids:
            placeholders = ", ".join("?" for _ in semantic_ids)
            text_clause = f"({text_clause} OR t.id IN ({placeholders}))"
            params += semantic_ids
        clauses.append(text_clause)

    if benefits:
        benefit_ids = __benefitIdsFor(benefits)
        if not benefit_ids:
            return []
        placeholders = ", ".join("?" for _ in benefit_ids)
        clauses.append(
            f"t.id IN (SELECT tea FROM Tea_benefit WHERE benefit IN ({placeholders}))"
        )
        params += benefit_ids

    if herbs:
        placeholders = ", ".join("?" for _ in herbs)
        clauses.append(
            f"t.id IN (SELECT tea FROM Ingredients WHERE herb IN ({placeholders}))"
        )
        params += herbs

    if is_tea is not None:
        clauses.append("t.is_tea = ?")
        params.append(1 if is_tea else 0)

    if has_caffeine is not None:
        clauses.append("t.has_caffeine = ?")
        params.append(1 if has_caffeine else 0)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = __get_db().execute(
        f"SELECT t.* FROM Tea t {where} ORDER BY t.name;", params
    ).fetchall()

    teas = [Models.Tea.model_validate(dict(row)) for row in rows]

    if sort == "name":
        return teas
    if sort == "name_desc":
        return list(reversed(teas))

    # Relevance: whatever the embedder ranked highest floats to the top.
    rank = {tea_id: i for i, tea_id in enumerate(semantic_ids or [])}
    return sorted(teas, key=lambda tea: (rank.get(tea.id, len(rank)), tea.name))

@current_app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
