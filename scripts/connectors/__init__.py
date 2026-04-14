# Camper Tracker MVP - Conectores
# Paquete de conectores para cada fuente de datos

from .base import BaseConnector
from .autoscout24 import AutoScout24Connector

__all__ = ["BaseConnector", "AutoScout24Connector"]
