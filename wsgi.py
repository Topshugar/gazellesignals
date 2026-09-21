from app import app, db, User
from admin_routes import init_admin

# Render should run this module with: gunicorn wsgi:app
init_admin(app, db, User)
