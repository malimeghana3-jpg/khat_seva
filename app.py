import os
import sqlite3
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------- APP CONFIGURATION ----------------

BASE_DIR = Path(__file__).resolve().parent

# static_folder="static" + static_url_path="" means /style.css is served
# from the "static" folder. This keeps app.py and khat_seva.db private.
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path=""
)

# On Render, set SECRET_KEY in Environment settings (any long random text).
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "khat-seva-change-this-secret-key"
)

DB_PATH = BASE_DIR / "khat_seva.db"


# ---------------- DATABASE CONNECTION ----------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    with get_db() as conn:

        # Farmers table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farmers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                mobile TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                village TEXT NOT NULL DEFAULT '',
                district TEXT NOT NULL DEFAULT '',
                land_details TEXT NOT NULL DEFAULT '',
                password_hash TEXT
            )
        """)

        # Upgrade existing database without deleting old records
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(farmers)")
        }

        migrations = {
            "password": "TEXT NOT NULL DEFAULT ''",
            "address": "TEXT NOT NULL DEFAULT ''",
            "village": "TEXT NOT NULL DEFAULT ''",
            "district": "TEXT NOT NULL DEFAULT ''",
            "land_details": "TEXT NOT NULL DEFAULT ''",
            "password_hash": "TEXT"
        }

        for column, definition in migrations.items():
            if column not in columns:
                conn.execute(
                    f"ALTER TABLE farmers ADD COLUMN {column} {definition}"
                )

        # Orders table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                farmer_id INTEGER NOT NULL,
                total REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (farmer_id) REFERENCES farmers(id)
            )
        """)

        # Order items table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)


# IMPORTANT: run at import time so it also works under gunicorn (Render).
# Before, this was only inside `if __name__ == "__main__":`, which gunicorn
# never runs, so the tables were never created on Render.
create_tables()


# ---------------- HOME PAGE ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip().lower()
        address = request.form.get("address", "").strip()
        village = request.form.get("village", "").strip()
        district = request.form.get("district", "").strip()
        land_details = request.form.get("land_details", "").strip()
        password = request.form.get("password", "")

        if not all([
            name, mobile, email, address, village,
            district, land_details, password
        ]):
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))

        if not mobile.isdigit() or len(mobile) != 10:
            flash("Enter a valid 10-digit mobile number.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        try:
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO farmers (
                        name, mobile, email, password, address,
                        village, district, land_details, password_hash
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, mobile, email, password_hash, address,
                    village, district, land_details, password_hash
                ))

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("This email is already registered.", "error")
            return redirect(url_for("register"))

        except sqlite3.Error:
            flash("Database error. Please try again.", "error")
            return redirect(url_for("register"))

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as conn:
            farmer = conn.execute(
                "SELECT * FROM farmers WHERE LOWER(email) = ?",
                (email,)
            ).fetchone()

            if farmer:
                stored_password = farmer["password"] or ""
                stored_hash = farmer["password_hash"] or ""

                # Check password hash from either column
                valid = False

                for saved in (stored_hash, stored_password):
                    if saved:
                        try:
                            if check_password_hash(saved, password):
                                valid = True
                                break
                        except (ValueError, TypeError):
                            pass

                # Support older accounts with plain-text passwords
                if not valid and stored_password == password:
                    valid = bool(password)

                if valid:
                    # Migrate older password formats safely
                    new_hash = generate_password_hash(password)
                    conn.execute("""
                        UPDATE farmers
                        SET password = ?, password_hash = ?
                        WHERE id = ?
                    """, (new_hash, new_hash, farmer["id"]))

                    session.clear()
                    session["farmer_id"] = farmer["id"]
                    session["farmer_name"] = farmer["name"]
                    session["farmer_email"] = farmer["email"]

                    return redirect(url_for("home"))

        return render_template(
            "login.html",
            error="Invalid Email or Password. Please check your details."
        )

    return render_template("login.html")


# ---------------- SEEDS ----------------

@app.route("/seeds")
def seeds():
    products = [
        {
            "id": 1,
            "name": "Cotton Seeds",
            "price": 850,
            "description": "Cotton seeds for agricultural farming.",
            "availability": "Available"
        },
        {
            "id": 2,
            "name": "Wheat Seeds",
            "price": 600,
            "description": "Quality seeds for wheat cultivation.",
            "availability": "Available"
        },
        {
            "id": 3,
            "name": "Soybean Seeds",
            "price": 750,
            "description": "Soybean seeds for seasonal farming.",
            "availability": "Available"
        }
    ]

    return render_template("seeds.html", products=products)


# ---------------- FERTILIZERS ----------------

@app.route("/fertilizers")
def fertilizers():
    products = [
        {
            "id": 4,
            "name": "Organic Fertilizer",
            "price": 450,
            "description": "Organic fertilizer for soil improvement.",
            "availability": "Available"
        },
        {
            "id": 5,
            "name": "NPK Fertilizer",
            "price": 900,
            "description": "NPK fertilizer for crop nutrition.",
            "availability": "Available"
        },
        {
            "id": 6,
            "name": "Vermicompost",
            "price": 350,
            "description": "Compost made using earthworms.",
            "availability": "Available"
        }
    ]

    return render_template("fertilizers.html", products=products)


# ---------------- PRODUCT CATALOGUE ----------------

CART_PRODUCTS = {
    1: {"name": "Cotton Seeds", "price": 850, "category": "Seeds"},
    2: {"name": "Wheat Seeds", "price": 600, "category": "Seeds"},
    3: {"name": "Soybean Seeds", "price": 750, "category": "Seeds"},
    4: {"name": "Organic Fertilizer", "price": 450, "category": "Fertilizers"},
    5: {"name": "NPK Fertilizer", "price": 900, "category": "Fertilizers"},
    6: {"name": "Vermicompost", "price": 350, "category": "Fertilizers"}
}


def farmer_logged_in():
    return "farmer_id" in session


# ---------------- ADD TO CART ----------------

@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if not farmer_logged_in():
        flash("Please log in before adding products to your cart.", "error")
        return redirect(url_for("login"))

    if product_id not in CART_PRODUCTS:
        flash("Product not found.", "error")
        return redirect(url_for("seeds"))

    cart_data = session.get("cart", {})
    key = str(product_id)

    cart_data[key] = int(cart_data.get(key, 0)) + 1
    session["cart"] = cart_data

    flash("Product added to cart!", "success")
    return redirect(url_for("cart"))


# ---------------- VIEW CART ----------------

@app.route("/cart")
def cart():
    if not farmer_logged_in():
        flash("Please log in to view your cart.", "error")
        return redirect(url_for("login"))

    cart_data = session.get("cart", {})
    items = []
    total = 0

    for product_id, quantity in cart_data.items():
        product = CART_PRODUCTS.get(int(product_id))

        if product and int(quantity) > 0:
            subtotal = product["price"] * int(quantity)

            items.append({
                "id": int(product_id),
                "name": product["name"],
                "price": product["price"],
                "quantity": int(quantity),
                "subtotal": subtotal
            })

            total += subtotal

    return render_template("cart.html", items=items, total=total)


# ---------------- UPDATE CART ----------------

@app.route("/update_cart/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    if not farmer_logged_in():
        return redirect(url_for("login"))

    cart_data = session.get("cart", {})
    key = str(product_id)

    try:
        quantity = int(request.form.get("quantity", "1"))
    except ValueError:
        flash("Please enter a valid quantity.", "error")
        return redirect(url_for("cart"))

    if product_id not in CART_PRODUCTS or key not in cart_data:
        flash("Product not found in cart.", "error")
    elif quantity < 1 or quantity > 100:
        flash("Quantity must be between 1 and 100.", "error")
    else:
        cart_data[key] = quantity
        session["cart"] = cart_data
        flash("Cart updated!", "success")

    return redirect(url_for("cart"))


# ---------------- REMOVE FROM CART ----------------

@app.route("/remove_from_cart/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    if not farmer_logged_in():
        return redirect(url_for("login"))

    cart_data = session.get("cart", {})
    cart_data.pop(str(product_id), None)
    session["cart"] = cart_data

    flash("Product removed from cart.", "success")
    return redirect(url_for("cart"))


# ---------------- PLACE ORDER ----------------

@app.route("/place_order", methods=["POST"])
def place_order():
    if not farmer_logged_in():
        flash("Please log in before placing an order.", "error")
        return redirect(url_for("login"))

    cart_data = session.get("cart", {})
    valid_items = []
    total = 0

    for product_id, quantity in cart_data.items():
        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except (ValueError, TypeError):
            continue

        product = CART_PRODUCTS.get(product_id)

        if product and 1 <= quantity <= 100:
            subtotal = product["price"] * quantity

            valid_items.append({
                "id": product_id,
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
                "subtotal": subtotal
            })

            total += subtotal

    if not valid_items:
        flash("Your cart is empty. Add products first.", "error")
        return redirect(url_for("cart"))

    try:
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO orders (farmer_id, total)
                VALUES (?, ?)
            """, (session["farmer_id"], total))

            order_id = cursor.lastrowid

            for item in valid_items:
                conn.execute("""
                    INSERT INTO order_items (
                        order_id, product_id, product_name,
                        quantity, price, subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    order_id,
                    item["id"],
                    item["name"],
                    item["quantity"],
                    item["price"],
                    item["subtotal"]
                ))

        session.pop("cart", None)
        flash(f"Order #{order_id} placed successfully!", "success")
        return redirect(url_for("orders"))
    except sqlite3.Error:
        flash("Unable to place order. Please try again.", "error")
        return redirect(url_for("cart"))


# ---------------- ORDER HISTORY ----------------

@app.route("/orders")
def orders():
    if "farmer_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            o.id AS order_id,
            o.total,
            o.created_at,
            f.name AS farmer_name,
            f.email AS farmer_email,
            f.mobile AS farmer_mobile,
            f.village AS farmer_village,
            f.district AS farmer_district
        FROM orders o
        JOIN farmers f ON o.farmer_id = f.id
        WHERE o.farmer_id = ?
        ORDER BY o.id DESC
    """, (session["farmer_id"],))

    orders_list = cur.fetchall()

    order_details = []

    for order in orders_list:
        cur.execute("""
            SELECT
                product_name,
                quantity,
                price,
                subtotal
            FROM order_items
            WHERE order_id = ?
        """, (order["order_id"],))

        items = cur.fetchall()

        order_details.append({
            "order": order,
            "items": items
        })

    conn.close()

    return render_template(
        "orders.html",
        order_details=order_details
    )


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# ---------------- RUN APPLICATION (LOCAL ONLY) ----------------
# On Render, gunicorn runs "app:app" and this block is skipped.

if __name__ == "__main__":
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, app)

    print("Khat Seva is running at http://127.0.0.1:" + str(server.server_port))

    server.serve_forever()