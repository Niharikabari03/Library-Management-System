# app.py
from flask import Flask, request, redirect, url_for, render_template_string, flash
import sqlite3
from datetime import datetime
import os

DB_NAME = 'library.db'
app = Flask(__name__)
app.secret_key = 'replace-this-with-a-random-secret'  # for flash messages

# ---------- DB helpers ----------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            year INTEGER,
            isbn TEXT UNIQUE,
            qty INTEGER DEFAULT 1
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS issued (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER,
            student_name TEXT,
            student_roll TEXT,
            issue_date TEXT,
            return_date TEXT,
            FOREIGN KEY(book_id) REFERENCES books(id)
        )
    ''')
    conn.commit()
    conn.close()

def run_query(query, params=(), fetch=True):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(query, params)
    if fetch:
        result = c.fetchall()
    else:
        result = None
    conn.commit()
    conn.close()
    return result

# Business logic functions
def add_book(title, author, year, isbn, qty):
    try:
        run_query('INSERT INTO books (title, author, year, isbn, qty) VALUES (?, ?, ?, ?, ?)',
                  (title, author, year if year else None, isbn if isbn else None, qty or 1), fetch=False)
        return True, "Book added."
    except sqlite3.IntegrityError:
        return False, "Book with same ISBN already exists."

def get_all_books():
    return run_query('SELECT id, title, author, year, isbn, qty FROM books ORDER BY title')

def search_books(term):
    like = f"%{term}%"
    return run_query('SELECT id, title, author, year, isbn, qty FROM books WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ? ORDER BY title',
                     (like, like, like))

def delete_book(book_id):
    run_query('DELETE FROM books WHERE id=?', (book_id,), fetch=False)

def issue_book(book_id, student_name, student_roll, issue_date):
    res = run_query('SELECT qty FROM books WHERE id=?', (book_id,))
    if not res:
        return False, 'Book not found'
    qty = res[0][0] or 0
    if qty <= 0:
        return False, 'No copies available'
    run_query('UPDATE books SET qty = qty - 1 WHERE id=?', (book_id,), fetch=False)
    run_query('INSERT INTO issued (book_id, student_name, student_roll, issue_date) VALUES (?, ?, ?, ?)',
              (book_id, student_name, student_roll, issue_date), fetch=False)
    return True, 'Issued'

def get_issued_books():
    return run_query('''
        SELECT i.id, b.title, i.student_name, i.student_roll, i.issue_date, i.return_date
        FROM issued i JOIN books b ON i.book_id = b.id
        ORDER BY i.issue_date DESC
    ''')

def return_book_db(issued_id, return_date):
    res = run_query('SELECT book_id, return_date FROM issued WHERE id = ?', (issued_id,))
    if not res:
        return False, "Issued record not found."
    book_id, current_return = res[0]
    if current_return is not None and str(current_return).strip() != '':
        return False, f"Already returned on {current_return}"
    run_query('UPDATE issued SET return_date = ? WHERE id = ? AND (return_date IS NULL OR trim(return_date) = "")',
              (return_date, issued_id), fetch=False)
    run_query('UPDATE books SET qty = qty + 1 WHERE id = ?', (book_id,), fetch=False)
    return True, "Return recorded."

# Initialize DB at startup
init_db()

# ---------- Simple templates (render_template_string used so app is single-file) ----------
BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Library Management</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- Bootstrap CDN (optional) -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-4">
  <h1 class="mb-3">Library Management System </h1>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      {% for m in messages %}
        <div class="alert alert-info">{{ m }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}
  <div class="row">
    <div class="col-md-7">
      {{ content|safe }}
    </div>
    <div class="col-md-5">
      <div class="card mb-3">
        <div class="card-body">
          <h5 class="card-title">Add Book</h5>
          <form method="post" action="{{ url_for('add_book_route') }}">
            <div class="mb-2"><input name="title" required class="form-control" placeholder="Title"></div>
            <div class="mb-2"><input name="author" class="form-control" placeholder="Author"></div>
            <div class="mb-2"><input name="year" class="form-control" placeholder="Year (e.g., 2020)"></div>
            <div class="mb-2"><input name="isbn" class="form-control" placeholder="ISBN"></div>
            <div class="mb-2"><input name="qty" class="form-control" placeholder="Quantity (1)"></div>
            <button class="btn btn-primary btn-sm">Add</button>
          </form>
        </div>
      </div>

      <div class="card">
        <div class="card-body">
          <h5 class="card-title">Actions</h5>
          <a href="{{ url_for('index') }}" class="btn btn-outline-secondary btn-sm mb-2">View All Books</a>
          <a href="{{ url_for('issued') }}" class="btn btn-outline-secondary btn-sm mb-2">Show Issued Books</a>
          <form method="get" action="{{ url_for('search') }}" class="mb-2">
            <div class="input-group">
              <input name="q" class="form-control form-control-sm" placeholder="Search title/author/isbn">
              <button class="btn btn-sm btn-outline-primary">Search</button>
            </div>
          </form>
        </div>
      </div>

    </div>
  </div>
</div>
</body>
</html>
"""

BOOKS_TABLE = """
<h4>Books</h4>
<table class="table table-sm table-striped">
<thead><tr><th>ID</th><th>Title</th><th>Author</th><th>Year</th><th>ISBN</th><th>Qty</th><th>Actions</th></tr></thead>
<tbody>
{% for b in books %}
  <tr>
    <td>{{ b[0] }}</td>
    <td>{{ b[1] }}</td>
    <td>{{ b[2] or '' }}</td>
    <td>{{ b[3] or '' }}</td>
    <td>{{ b[4] or '' }}</td>
    <td>{{ b[5] }}</td>
    <td>
      <a href="{{ url_for('issue_form', book_id=b[0]) }}" class="btn btn-sm btn-success">Issue</a>
      <a href="{{ url_for('delete_book_route', book_id=b[0]) }}" class="btn btn-sm btn-danger" onclick="return confirm('Delete this book?')">Delete</a>
    </td>
  </tr>
{% endfor %}
</tbody>
</table>
"""

ISSUED_TABLE = """
<h4>Issued Books</h4>
<table class="table table-sm table-striped">
<thead><tr><th>ID</th><th>Title</th><th>Student</th><th>Roll</th><th>Issue Date</th><th>Return Date</th><th>Actions</th></tr></thead>
<tbody>
{% for i in issued %}
  <tr>
    <td>{{ i[0] }}</td>
    <td>{{ i[1] }}</td>
    <td>{{ i[2] }}</td>
    <td>{{ i[3] }}</td>
    <td>{{ i[4] or '' }}</td>
    <td>{{ i[5] or '' }}</td>
    <td>
      {% if not i[5] %}
        <a href="{{ url_for('return_form', issued_id=i[0]) }}" class="btn btn-sm btn-warning">Return</a>
      {% else %}
        <span class="text-muted">Returned</span>
      {% endif %}
    </td>
  </tr>
{% endfor %}
</tbody>
</table>
"""

ISSUE_FORM = """
<h4>Issue Book: {{ book[1] if book else '' }}</h4>
<form method="post" action="{{ url_for('issue_book_route', book_id=book[0]) }}">
  <div class="mb-2"><input name="student_name" required class="form-control" placeholder="Student name"></div>
  <div class="mb-2"><input name="student_roll" required class="form-control" placeholder="Student roll"></div>
  <div class="mb-2"><input name="issue_date" class="form-control" value="{{today}}"></div>
  <button class="btn btn-primary btn-sm">Issue</button>
</form>
"""

RETURN_FORM = """
<h4>Return Issued ID: {{ issued_id }}</h4>
<form method="post" action="{{ url_for('return_book_route', issued_id=issued_id) }}">
  <div class="mb-2"><input name="return_date" class="form-control" value="{{today}}"></div>
  <button class="btn btn-primary btn-sm">Return</button>
</form>
"""

# ---------- Routes ----------
@app.route('/')
def index():
    books = get_all_books()
    content = render_template_string(BOOKS_TABLE, books=books)
    return render_template_string(BASE_HTML, content=content)

@app.route('/add', methods=['POST'])
def add_book_route():
    title = request.form.get('title','').strip()
    author = request.form.get('author','').strip()
    year = request.form.get('year','').strip()
    isbn = request.form.get('isbn','').strip()
    qty = request.form.get('qty','').strip()
    try:
        qty = int(qty) if qty else 1
    except ValueError:
        qty = 1
    ok, msg = add_book(title, author, int(year) if year else None, isbn, qty)
    flash(msg)
    return redirect(url_for('index'))

@app.route('/delete/<int:book_id>')
def delete_book_route(book_id):
    delete_book(book_id)
    flash("Book deleted.")
    return redirect(url_for('index'))

@app.route('/search')
def search():
    q = request.args.get('q','').strip()
    if not q:
        return redirect(url_for('index'))
    books = search_books(q)
    content = render_template_string(BOOKS_TABLE, books=books)
    return render_template_string(BASE_HTML, content=content)

@app.route('/issue/<int:book_id>', methods=['GET','POST'])
def issue_form(book_id):
    # GET -> show issue form
    if request.method == 'GET':
        books = get_all_books()
        book = next((b for b in books if b[0]==book_id), None)
        today = datetime.today().strftime('%Y-%m-%d')
        content = render_template_string(ISSUE_FORM, book=book, today=today)
        return render_template_string(BASE_HTML, content=content)
    # POST handled by issue_book_route
    return redirect(url_for('index'))

@app.route('/issue_book/<int:book_id>', methods=['POST'])
def issue_book_route(book_id):
    name = request.form.get('student_name','').strip()
    roll = request.form.get('student_roll','').strip()
    issue_date = request.form.get('issue_date','').strip() or ''
    ok, msg = issue_book(book_id, name, roll, issue_date)
    flash(msg)
    return redirect(url_for('index'))

@app.route('/issued')
def issued():
    issued = get_issued_books()
    content = render_template_string(ISSUED_TABLE, issued=issued)
    return render_template_string(BASE_HTML, content=content)

@app.route('/return/<int:issued_id>', methods=['GET','POST'])
def return_form(issued_id):
    if request.method == 'GET':
        today = datetime.today().strftime('%Y-%m-%d')
        content = render_template_string(RETURN_FORM, issued_id=issued_id, today=today)
        return render_template_string(BASE_HTML, content=content)
    # POST handled by return_book_route
    return redirect(url_for('issued'))

@app.route('/return_book/<int:issued_id>', methods=['POST'])
def return_book_route(issued_id):
    user_date = request.form.get('return_date','').strip()
    if not user_date:
        user_date = datetime.today().strftime('%Y-%m-%d')
    # Validate basic format
    try:
        datetime.strptime(user_date, '%Y-%m-%d')
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.")
        return redirect(url_for('issued'))
    ok, msg = return_book_db(issued_id, user_date)
    flash(msg)
    return redirect(url_for('issued'))

# Run app
if __name__ == '__main__':
    # Ensure DB file exists
    if not os.path.exists(DB_NAME):
        init_db()
    app.run(debug=True)
