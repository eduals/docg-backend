from datetime import datetime
from app.database import db

class PKCEVerifier(db.Model):
    """Armazenamento temporário de code_verifier para PKCE OAuth"""
    __tablename__ = 'pkce_verifiers'
    
    state = db.Column(db.String(255), primary_key=True, nullable=False, index=True)
    code_verifier = db.Column(db.Text, nullable=False)
    frontend_redirect_uri = db.Column(db.String(500), nullable=True)  # Para redirecionar frontend após callback
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<PKCEVerifier {self.state}>'

