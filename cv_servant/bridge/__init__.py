"""
CV Servant Bridge Package.
Contains the local REST API server facilitating live communication with the Chrome Extension.
"""
from cv_servant.bridge.api_server import CVBridgeServer, get_candidate_autofill_data

__all__ = ["CVBridgeServer", "get_candidate_autofill_data"]
