"""Shared settings helpers for the RF Planner plugin."""

import json

from qgis.PyQt.QtCore import QSettings


class PluginSettings:
    API_URL_KEY = "rf_planner/api_url"
    COVERAGE_PARAMETERS_KEY = "rf_planner/coverage_parameters"

    @classmethod
    def get_api_url(cls) -> str:
        value = QSettings().value(cls.API_URL_KEY, "", type=str)
        return value.strip()

    @classmethod
    def set_api_url(cls, api_url: str) -> None:
        QSettings().setValue(cls.API_URL_KEY, api_url.strip())

    @classmethod
    def get_geoserver_base_url(cls) -> str:
        api_url = cls.get_api_url().rstrip("/")
        if api_url.endswith("/api"):
            return api_url[:-4] + "/geoserver"
        return api_url.replace("/api", "/geoserver")

    @classmethod
    def set_coverage_parameters(cls, params: dict) -> None:
        QSettings().setValue(cls.COVERAGE_PARAMETERS_KEY, json.dumps(params))

    @classmethod
    def get_coverage_parameters(cls) -> dict:
        raw = QSettings().value(cls.COVERAGE_PARAMETERS_KEY, "", type=str)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
