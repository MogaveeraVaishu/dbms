from flask import Flask, render_template, request, redirect, session
from database import get_connection
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "canteen_secret_key"


@app.route('/')
def home():
    return redirect('/login')

@app.route('/menu')
def menu():

    if 'user_id' not in session:
        return redirect('/login')

    con = get_connection()
    cur = con.cursor()

    cur.execute("SELECT * FROM Food_Items")
    food = cur.fetchall()

    cur.close()
    con.close()

    return render_template('menu.html', food=food)

@app.route('/add_to_cart/<int:food_id>', methods=['POST'])
def add_to_cart(food_id):

    quantity = int(request.form['quantity'])

    if quantity <= 0:
        return "Invalid quantity", 400

    con = get_connection()
    cur = con.cursor()

    cur.execute(
        "SELECT stock_quantity, availability FROM Food_Items WHERE food_id = %s",
        (food_id,)
    )

    item = cur.fetchone()

    cur.close()
    con.close()

    if item is None:
        return "Food item not found", 404

    if not item[1] or item[0] < quantity:
        return "Insufficient stock or item unavailable", 400

    cart = session.get('cart', {})

    current_quantity = cart.get(str(food_id), 0)

    if current_quantity + quantity > item[0]:
        return "Requested quantity exceeds available stock", 400

    cart[str(food_id)] = current_quantity + quantity

    session['cart'] = cart

    return redirect('/cart')


@app.route('/cart')
def cart():

    cart_items = []
    total = 0

    con = get_connection()
    cur = con.cursor()

    for food_id, quantity in session.get('cart', {}).items():

        cur.execute(
            "SELECT food_id, food_name, price FROM Food_Items WHERE food_id = %s",
            (int(food_id),)
        )

        item = cur.fetchone()

        if item:
            subtotal = item[2] * quantity

            cart_items.append({
                'id': item[0],
                'name': item[1],
                'price': item[2],
                'quantity': quantity,
                'subtotal': subtotal
            })

            total += subtotal

    cur.close()
    con.close()

    return render_template(
        'cart.html',
        cart_items=cart_items,
        total=total
    )


@app.route('/remove_from_cart/<int:food_id>')
def remove_from_cart(food_id):

    cart = session.get('cart', {})

    cart.pop(str(food_id), None)

    session['cart'] = cart

    return redirect('/cart')


# STUDENT REGISTRATION

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        phone = request.form['phone']

        con = get_connection()
        cur = con.cursor()

        cur.execute(
            "SELECT user_id FROM Users WHERE email = %s",
            (email,)
        )

        if cur.fetchone():
            cur.close()
            con.close()
            return "Email already registered!"

        cur.execute(
            """INSERT INTO Users(name, email, password, phone, role)
               VALUES(%s, %s, %s, %s, 'Student')""",
            (name, email, password, phone)
        )

        con.commit()

        cur.close()
        con.close()

        return redirect('/login')

    return render_template('register.html')


# STUDENT / ADMIN LOGIN

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        con = get_connection()
        cur = con.cursor()

        cur.execute(
            "SELECT * FROM Users WHERE email = %s",
            (email,)
        )

        user = cur.fetchone()

        if user:

            stored_password = user[3]

            if stored_password.startswith('scrypt:'):
                valid = check_password_hash(stored_password, password)
            else:
                valid = stored_password == password

                if valid:
                    stored_password = generate_password_hash(password)

                    cur.execute(
                        "UPDATE Users SET password = %s WHERE user_id = %s",
                        (stored_password, user[0])
                    )

                    con.commit()

            if valid:

                session.clear()

                session['user_id'] = user[0]
                session['name'] = user[1]
                session['role'] = user[5]

                cur.close()
                con.close()

                if user[5] == 'Admin':
                    return redirect('/admin')

                return redirect('/menu')

        cur.close()
        con.close()

        return "Invalid email or password!"

    return render_template('login.html')


# LOGOUT

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')


@app.route('/admin')
def admin():

    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect('/login')

    con = get_connection()
    cur = con.cursor()

    cur.execute("SELECT * FROM Food_Items ORDER BY food_id")
    food = cur.fetchall()

    cur.execute("""
        SELECT order_id, user_id, order_date, total_amount, status
        FROM Orders
        ORDER BY order_id DESC
    """)

    orders = cur.fetchall()

    # Added: Fetch categories
    cur.execute("SELECT * FROM Categories")
    categories = cur.fetchall()

    cur.close()
    con.close()

    return render_template(
        'admin.html',
        food=food,
        orders=orders,
        categories=categories
    )


@app.route('/add_food', methods=['POST'])
def add_food():

    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect('/login')

    name = request.form['food_name']
    category = request.form['category_id']
    price = request.form['price']
    stock = request.form['stock_quantity']

    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO Food_Items
        (food_name, category_id, price, stock_quantity, availability)
        VALUES (%s, %s, %s, %s, TRUE)
    """, (name, category, price, stock))

    con.commit()
    cur.close()
    con.close()

    return redirect('/admin')


@app.route('/update_food/<int:food_id>', methods=['POST'])
def update_food(food_id):

    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect('/login')

    name = request.form['food_name']
    category = request.form['category_id']
    price = request.form['price']
    stock = request.form['stock_quantity']

    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        UPDATE Food_Items
        SET food_name = %s,
            category_id = %s,
            price = %s,
            stock_quantity = %s
        WHERE food_id = %s
    """, (name, category, price, stock, food_id))

    con.commit()
    cur.close()
    con.close()

    return redirect('/admin')


@app.route('/delete_food/<int:food_id>', methods=['POST'])
def delete_food(food_id):

    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect('/login')

    con = get_connection()
    cur = con.cursor()

    cur.execute(
        "DELETE FROM Food_Items WHERE food_id = %s",
        (food_id,)
    )

    con.commit()
    cur.close()
    con.close()

    return redirect('/admin')


@app.route('/checkout', methods=['POST'])
def checkout():

    if 'user_id' not in session:
        return redirect('/login')

    cart = session.get('cart', {})

    if not cart:
        return "Your cart is empty!"

    payment_mode = request.form['payment_mode']

    con = get_connection()
    cur = con.cursor()

    try:
        total = 0
        items = []

        # Calculate total amount
        for food_id, quantity in cart.items():

            cur.execute("""
                SELECT food_id, price, stock_quantity, availability
                FROM Food_Items
                WHERE food_id = %s
            """, (int(food_id),))

            item = cur.fetchone()

            if item is None or not item[3] or item[2] < quantity:
                raise Exception("Food unavailable or insufficient stock!")

            total += item[1] * quantity

            items.append((item[0], quantity, item[1]))

        # Create order
        cur.execute("""
            INSERT INTO Orders(user_id, total_amount, status)
            VALUES(%s, %s, 'Pending')
            RETURNING order_id
        """, (session['user_id'], total))

        order_id = cur.fetchone()[0]

        # Insert order items
        for food_id, quantity, price in items:

            cur.execute("""
                INSERT INTO Order_Items
                (order_id, food_id, quantity, unit_price)
                VALUES(%s, %s, %s, %s)
            """, (order_id, food_id, quantity, price))

        # Insert payment details
        cur.execute("""
            INSERT INTO Payments
            (order_id, amount, payment_mode, payment_status)
            VALUES(%s, %s, %s, 'Paid')
        """, (order_id, total, payment_mode))

        con.commit()

        session['cart'] = {}

        return render_template(
            'order_success.html',
            order_id=order_id,
            total=total
        )

    except Exception as e:
        con.rollback()
        return str(e), 400

    finally:
        cur.close()
        con.close()


# STUDENT ORDER HISTORY

@app.route('/my_orders')
def my_orders():

    if 'user_id' not in session or session.get('role') != 'Student':
        return redirect('/login')

    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        SELECT 
            o.order_id,
            o.order_date,
            o.total_amount,
            o.status,
            oi.food_id,
            f.food_name,
            oi.quantity,
            oi.unit_price
        FROM Orders o
        JOIN Order_Items oi ON o.order_id = oi.order_id
        JOIN Food_Items f ON oi.food_id = f.food_id
        WHERE o.user_id = %s
        ORDER BY o.order_date DESC
    """, (session['user_id'],))

    orders = cur.fetchall()

    cur.close()
    con.close()

    return render_template('order_history.html', orders=orders)

@app.route('/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):

    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect('/login')

    status = request.form['status']

    allowed_status = ['Pending', 'Preparing', 'Completed', 'Cancelled']

    if status not in allowed_status:
        return redirect('/admin')

    con = get_connection()
    cur = con.cursor()

    cur.execute(
        "UPDATE Orders SET status = %s WHERE order_id = %s",
        (status, order_id)
    )

    con.commit()
    cur.close()
    con.close()

    return redirect('/admin')
if __name__ == '__main__':
    app.run(debug=True)