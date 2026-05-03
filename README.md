// support portal backend
## 🚀 Backend Setup (Flask)

### 1. Clone the repository

```
git clone <your-repo-url>
cd support-portal-backend
```

### 2. Create virtual environment

```
python -m venv venv
```

### 3. Activate virtual environment (Windows)

```
venv\Scripts\activate
```

### 4. Install dependencies

```
pip install -r requirements.txt
```

### 5. Initialize database

```
python init_db.py
```

### 6. Run the server

```
python app.py
```

### 7. Access API

```
http://localhost:5000/api/tickets
```
## 🗄️ Database Setup

### Initialize database

```id="kztkzn"
python init_db.py
```

### ⚠️ When to run this command?

* First time setup
* After adding new models (e.g., User)
* After changing schema (columns, tables)
* After deleting/resetting database

### ❌ When NOT to run?

* Do not run on every server start
* Do not run if database is already initialized

### Reset database (if schema mismatch error occurs)

```id="n5wx6y"
# delete existing DB file
del tickets.db   # Windows

# recreate database
python init_db.py
```
