"""Shared settings helpers for the RF Planner plugin."""

import json
import hashlib
import os

from qgis.PyQt.QtCore import QSettings
from qgis.core import QgsProject


class PluginSettings:
    API_URL_KEY = "rf_planner/api_url"
    COVERAGE_PARAMETERS_KEY = "rf_planner/coverage_parameters"
    SCENARIO_STORE_PREFIX = "rf_planner/scenarios"

    @classmethod
    def _scope_hash(cls, value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def normalize_scenario_name(cls, scenario_name: str) -> str:
        name = str(scenario_name).strip()
        if name.endswith("*"):
            name = name[:-1].strip()
        return name

    @classmethod
    def _project_path_raw(cls) -> str:
        return QgsProject.instance().fileName().strip()

    @classmethod
    def _project_path_normalized(cls) -> str:
        project_path = cls._project_path_raw()
        if not project_path:
            return "untitled"
        return os.path.normcase(os.path.normpath(project_path))

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

    @classmethod
    def _project_scope_key(cls) -> str:
        return cls._scope_hash(cls._project_path_normalized())

    @classmethod
    def _untitled_scope_key(cls) -> str:
        return cls._scope_hash("untitled")

    @classmethod
    def _scenario_store_key(cls) -> str:
        return f"{cls.SCENARIO_STORE_PREFIX}/{cls._project_scope_key()}"

    @classmethod
    def _scenario_store_key_for_scope(cls, scope_key: str) -> str:
        return f"{cls.SCENARIO_STORE_PREFIX}/{scope_key}"

    @classmethod
    def _read_store(cls, key: str) -> dict:
        raw = QSettings().value(key, "", type=str)
        if not raw:
            return {"last": "", "scenarios": {}}
        try:
            store = json.loads(raw)
            if not isinstance(store, dict):
                return {"last": "", "scenarios": {}}
            store.setdefault("last", "")
            store.setdefault("scenarios", {})
            if not isinstance(store["scenarios"], dict):
                store["scenarios"] = {}
            normalized_scenarios = {}
            for scenario_name, params in store["scenarios"].items():
                clean_name = cls.normalize_scenario_name(scenario_name)
                normalized_scenarios[clean_name] = params
            store["scenarios"] = normalized_scenarios
            store["last"] = cls.normalize_scenario_name(store.get("last", ""))
            return store
        except json.JSONDecodeError:
            return {"last": "", "scenarios": {}}

    @classmethod
    def _write_store(cls, key: str, store: dict) -> None:
        QSettings().setValue(key, json.dumps(store))

    @classmethod
    def _ensure_scope_migration(cls) -> None:
        project_path_raw = cls._project_path_raw()
        if not project_path_raw:
            return

        normalized_scope = cls._project_scope_key()
        active_key = cls._scenario_store_key_for_scope(normalized_scope)
        active_store = cls._read_store(active_key)
        if active_store.get("scenarios"):
            return

        # Legacy fallback: old versions hashed the raw fileName() directly.
        legacy_scope = cls._scope_hash(project_path_raw)
        if legacy_scope != normalized_scope:
            legacy_key = cls._scenario_store_key_for_scope(legacy_scope)
            legacy_store = cls._read_store(legacy_key)
            if legacy_store.get("scenarios"):
                cls._write_store(active_key, legacy_store)
                return

        untitled_key = cls._scenario_store_key_for_scope(cls._untitled_scope_key())
        untitled_store = cls._read_store(untitled_key)
        if untitled_store.get("scenarios"):
            cls._write_store(active_key, untitled_store)

    @classmethod
    def get_scenario_store(cls) -> dict:
        cls._ensure_scope_migration()
        return cls._read_store(cls._scenario_store_key())

    @classmethod
    def set_scenario_store(cls, store: dict) -> None:
        cls._write_store(cls._scenario_store_key(), store)

    @classmethod
    def list_scenarios(cls) -> list[str]:
        store = cls.get_scenario_store()
        return sorted(store.get("scenarios", {}).keys())

    @classmethod
    def get_scenario(cls, scenario_name: str) -> dict:
        store = cls.get_scenario_store()
        return store.get("scenarios", {}).get(scenario_name, {})

    @classmethod
    def save_scenario(cls, scenario_name: str, params: dict) -> None:
        scenario_name = cls.normalize_scenario_name(scenario_name)
        if not scenario_name:
            raise ValueError("Scenario name cannot be empty.")

        store = cls.get_scenario_store()
        store.setdefault("scenarios", {})[scenario_name] = params
        store["last"] = scenario_name
        cls.set_scenario_store(store)

    @classmethod
    def delete_scenario(cls, scenario_name: str) -> None:
        scenario_name = cls.normalize_scenario_name(scenario_name)
        if not scenario_name:
            return

        store = cls.get_scenario_store()
        scenarios = store.get("scenarios", {})
        scenarios.pop(scenario_name, None)
        if store.get("last") == scenario_name:
            store["last"] = ""
        cls.set_scenario_store(store)

    @classmethod
    def get_last_scenario_name(cls) -> str:
        return str(cls.get_scenario_store().get("last", ""))

    @classmethod
    def set_last_scenario_name(cls, scenario_name: str) -> None:
        name = cls.normalize_scenario_name(scenario_name)
        store = cls.get_scenario_store()
        if name and name in store.get("scenarios", {}):
            store["last"] = name
        else:
            store["last"] = ""
        cls.set_scenario_store(store)
