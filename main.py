import os
from uuid import uuid4

from flask import Flask, request, jsonify, render_template, abort

from model.embedderSearch import SearchEmbedder

app = Flask(__name__)
app.config["DATABASE_URL"] = "dataMining/tea.db"
app.config["SECRET_KEY"] = str(uuid4())
app.config["SESSION_PERMANENT"] = False

with app.app_context():
    from database import Database

# items=6 so a product page can still show 5 neighbours after dropping itself.
model = SearchEmbedder(distance=0.45, items=6)

# The FAISS indexes were built from "SELECT id FROM Tea" in id order, so an
# index position p refers to tea id p + 1.
def to_tea_ids(positions: list[int]) -> list[int]:
    return [position + 1 for position in positions]

@app.route("/")
def index():
    categories = Database.getCategories(limit=8)
    featured = Database.searchProducts(sort="name")[:8]
    return render_template(
        "index.html",
        categories=categories,
        featured=featured,
        benefits_by_tea=Database.getBenefitsByTea([tea.id for tea in featured]),
        tea_count=Database.countProducts(),
        herb_count=Database.countHerbs(),
    )

@app.route("/search")
def search_name():
    name = request.args.get("name")

    indexes = to_tea_ids(model.search_name(name))

    if len(indexes) == 0:
        return jsonify({"message": "No data found"}), 400

    return [tea.model_dump() for tea in Database.getProductByIds(indexes)]

@app.route("/description")
def search_description():
    tea_id = int(request.args.get("id"))

    tea_data = Database.getProductById(tea_id)

    indexes = to_tea_ids(model.search_description(tea_data.description))

    if len(indexes) == 0:
        return jsonify({"message": "No data found"}), 400

    return [tea.model_dump() for tea in Database.getProductByIds(indexes)]

@app.route("/search_page")
def search_page():
    name = request.args.get("name", "").strip()
    selected_benefits = request.args.getlist("benefit")
    selected_herbs = request.args.getlist("herb")
    kind = request.args.get("kind", "")
    caffeine = request.args.get("caffeine", "")
    sort = request.args.get("sort", "relevance")

    semantic_ids = to_tea_ids(model.search_name(name)) if name else []

    results = Database.searchProducts(
        query=name or None,
        benefits=selected_benefits,
        herbs=selected_herbs,
        is_tea={"tea": True, "herbal": False}.get(kind),
        has_caffeine={"yes": True, "no": False}.get(caffeine),
        semantic_ids=semantic_ids,
        sort=sort,
    )

    return render_template(
        "search.html",
        results=results,
        benefits_by_tea=Database.getBenefitsByTea([tea.id for tea in results]),
        all_benefits=Database.getAllBenefits(),
        all_herbs=Database.getAllHerbNames(),
        query=name,
        selected_benefits=selected_benefits,
        selected_herbs=selected_herbs,
        kind=kind,
        caffeine=caffeine,
        sort=sort,
        semantic_hits=semantic_ids,
    )

@app.route("/product_page")
def get_product_page():
    try:
        id = int(request.args.get("id", ""))
    except ValueError:
        abort(404)

    tea_data = Database.getProductByIdOrNone(id)
    if tea_data is None:
        abort(404)

    similar_ids = [i for i in to_tea_ids(model.search_description(tea_data.description))
                   if i != tea_data.id][:5]
    similar = Database.getProductByIds(similar_ids) if similar_ids else []
    order = {tea_id: i for i, tea_id in enumerate(similar_ids)}
    similar.sort(key=lambda tea: order[tea.id])

    return render_template(
        "product.html",
        tea=tea_data,
        ingredients=Database.getIngredients(tea_data.id),
        faqs=Database.getFaqs(tea_data.id),
        benefits=Database.getBenefitsForTea(tea_data.id),
        similar=similar,
        benefits_by_tea=Database.getBenefitsByTea(similar_ids),
    )

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404

app.run(port=int(os.environ.get("PORT", 8083)))
