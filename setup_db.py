import sys
sys.path.insert(0, 'app')
from app import create_app
from models import db, Usuario

app = create_app()
with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(email='darilod2@gmail.com').first():
        u = Usuario(nome='Admin', email='darilod2@gmail.com', admin=True, ativo=True)
        u.set_senha('admin123')
        db.session.add(u)
        db.session.commit()
        print('Tabelas criadas e usuario admin cadastrado')
    else:
        print('Tabelas criadas. Usuario ja existe.')
