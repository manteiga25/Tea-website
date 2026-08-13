"""SQLAlchemy mappings for the tables the data-mining notebooks already built.

Nothing here creates or migrates anything — `tea.db` is the source of truth and
these classes just describe it so queries can be written in Python instead of
SQL strings.

The relationships are all `viewonly=True`: the site only reads, and that keeps
SQLAlchemy from ever trying to write through an association table.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Association tables. Each carries its own surrogate id in the database, but as
# far as the site is concerned they are plain many-to-many joins.
tea_benefit = Table(
    "Tea_benefit", Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("tea", ForeignKey("Tea.id"), nullable=False),
    Column("benefit", ForeignKey("Benefit.id"), nullable=False),
)

herb_benefit = Table(
    "Herb_benefit", Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("benefit", ForeignKey("Benefit.id"), nullable=False),
    Column("herb", ForeignKey("Herb.id"), nullable=False),
)

# Note this one joins to Herb by *name*, not id — that is how the scraper
# wrote it, and the foreign key in the database says so too.
ingredients = Table(
    "Ingredients", Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("tea", ForeignKey("Tea.id"), nullable=False),
    Column("herb", ForeignKey("Herb.name"), nullable=False),
)


class Tea(Base):
    __tablename__ = "Tea"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text)
    is_tea: Mapped[bool] = mapped_column(Boolean)
    has_caffeine: Mapped[bool] = mapped_column(Boolean)
    url: Mapped[str] = mapped_column(Text, unique=True)
    img_url: Mapped[str] = mapped_column(Text, unique=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    warning: Mapped[str | None] = mapped_column(Text)
    cook: Mapped[str] = mapped_column(Text)
    benefit_headline: Mapped[str | None] = mapped_column(Text)

    # Ordered by the Ingredients row id so the herbs keep the order the
    # product page lists them in.
    herbs: Mapped[list[Herb]] = relationship(
        secondary=ingredients, order_by=ingredients.c.id, viewonly=True)
    benefits: Mapped[list[Benefit]] = relationship(
        secondary=tea_benefit, order_by="Benefit.benefit", viewonly=True)
    faqs: Mapped[list[Faq]] = relationship(order_by="Faq.id", viewonly=True)


class Herb(Base):
    __tablename__ = "Herb"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)
    description: Mapped[str] = mapped_column(Text, unique=True)
    family_name: Mapped[str | None] = mapped_column(String(30))
    part_used: Mapped[str] = mapped_column(String(20))
    image_url: Mapped[str] = mapped_column(Text)

    benefits: Mapped[list[Benefit]] = relationship(
        secondary=herb_benefit, order_by="Benefit.benefit", viewonly=True)


class Benefit(Base):
    __tablename__ = "Benefit"

    id: Mapped[int] = mapped_column(primary_key=True)
    benefit: Mapped[str] = mapped_column(Text, unique=True)


class Faq(Base):
    __tablename__ = "Faq"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    tea: Mapped[int] = mapped_column(ForeignKey("Tea.id"))
