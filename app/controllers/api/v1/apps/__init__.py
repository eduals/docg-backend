"""Apps API Controllers"""
from flask import Blueprint

apps_bp = Blueprint('apps', __name__)

from . import dynamic_fields_controller
