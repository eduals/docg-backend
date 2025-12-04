# Este arquivo está vazio - endpoints legados foram removidos
# Endpoints de features foram migrados para usar DataSourceConnection
from flask import Blueprint

features_bp = Blueprint('features', __name__, url_prefix='/api/v1/features')

