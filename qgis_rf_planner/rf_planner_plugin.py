"""Main QGIS plugin entry point for RF Planner."""

import os
import threading
import time
import urllib.request
from urllib.parse import urlencode

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QAction
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsRasterLayer,
    QgsPointXY,
    QgsMessageLog,
    QgsLayerTreeGroup,
    Qgis,
)
from qgis.gui import QgsMapToolEmitPoint

from .api_client import ApiClient
from .dockwidget import DockWidget
from .settings import PluginSettings


class RFPlannerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock_widget = None
        self.api_client = ApiClient()
        self._pick_tool = None
        self._previous_map_tool = None

    def initGui(self):
        self.action = QAction("RF Planner", self.iface.mainWindow())
        self.action.triggered.connect(self.show_dock_widget)
        self.iface.addPluginToMenu("RF Planner", self.action)
        self.iface.addToolBarIcon(self.action)

        self._ensure_dock_widget()

        self.api_client.connectionSucceeded.connect(self._on_connection_success)
        self.api_client.connectionFailed.connect(self._on_connection_failed)
        self.api_client.coverageSubmitted.connect(self._on_coverage_submitted)
        self.api_client.coverageCompleted.connect(self._on_coverage_completed)
        self.api_client.coverageFailed.connect(self._on_coverage_failed)
        self.api_client.debugMessage.connect(self._on_debug_message)
        QgsProject.instance().layerWillBeRemoved.connect(self._on_layer_will_be_removed)
        self._cleanup_orphan_radio_planning_files_on_startup()

    def unload(self):
        try:
            QgsProject.instance().layerWillBeRemoved.disconnect(self._on_layer_will_be_removed)
        except TypeError:
            pass
        if self.action is not None:
            self.iface.removePluginMenu("RF Planner", self.action)
            self.iface.removeToolBarIcon(self.action)
        if self.dock_widget is not None:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

    def show_dock_widget(self):
        self._ensure_dock_widget()

        # Keep plugin UX deterministic: opening the panel always docks it on the right.
        if self.dock_widget.isFloating():
            self.dock_widget.setFloating(False)
        self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widget)

        self.dock_widget.show()
        self.dock_widget.raise_()
        self.dock_widget.activateWindow()

    def _save_api_url_from_dock(self, api_url: str):
        clean_url = api_url.strip()
        content = self._dock_content()
        if not clean_url:
            if content is not None:
                content.set_status("API URL is empty.", is_error=True)
                content.append_debug("Save aborted: API URL is empty.")
            return

        PluginSettings.set_api_url(clean_url)
        if content is not None:
            content.set_api_url(clean_url)
            content.set_status("API URL saved.")
            content.append_debug(f"Saved API URL: {clean_url}")

    def _on_connection_success(self, message: str) -> None:
        if self.dock_widget is not None:
            content = self.dock_widget.widget()
            if hasattr(content, "set_status"):
                content.set_status(message)

    def _on_connection_failed(self, message: str) -> None:
        if self.dock_widget is not None:
            content = self.dock_widget.widget()
            if hasattr(content, "set_status"):
                content.set_status(message, is_error=True)

    def run_coverage(self):
        content = self._dock_content()
        if content is None:
            self.show_dock_widget()
            content = self._dock_content()
        if content is None:
            return

        api_url = PluginSettings.get_api_url()
        if not api_url:
            content.set_status("Set the API URL before running coverage.", is_error=True)
            return

        latitude, longitude = content.coverage_location()
        payload = content.coverage_payload_defaults()
        payload.update({"lat": latitude, "lon": longitude})

        PluginSettings.set_coverage_parameters(content.coverage_parameters())

        content.set_status("Submitting coverage task...")
        content.append_debug("Submitting coverage task...")
        self.api_client.submit_coverage(api_url, payload)

    def _start_coordinate_pick(self):
        content = self._dock_content()
        if content is None:
            return

        canvas = self.iface.mapCanvas()
        self._previous_map_tool = canvas.mapTool()

        if self._pick_tool is None:
            self._pick_tool = QgsMapToolEmitPoint(canvas)
            self._pick_tool.canvasClicked.connect(self._on_map_clicked)

        canvas.setMapTool(self._pick_tool)
        content.set_status("Click on map to pick coverage coordinates.")
        content.append_debug("Pipette enabled: waiting for map click.")

    def _on_map_clicked(self, point, mouse_button):
        content = self._dock_content()
        if content is None:
            self._restore_previous_map_tool()
            return

        source_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        target_crs = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())

        try:
            geographic_point = transform.transform(QgsPointXY(point.x(), point.y()))
            lat = geographic_point.y()
            lon = geographic_point.x()
            content.set_coverage_location(lat, lon)
            content.set_status(f"Picked coordinates: {lat:.6f}, {lon:.6f}")
            content.append_debug(
                f"Map click transformed to EPSG:4326 lat={lat:.6f}, lon={lon:.6f}; button={mouse_button}"
            )
        except Exception as error:
            content.set_status(f"Failed to convert picked point: {error}", is_error=True)
            content.append_debug(f"Point transform failed: {error}")
        finally:
            self._restore_previous_map_tool()

    def _on_coverage_submitted(self, task_id: str) -> None:
        content = self._dock_content()
        if content is not None:
            content.set_status(f"Coverage task submitted: {task_id}")
            content.append_debug(f"Coverage task submitted: {task_id}")

    def _on_coverage_completed(self, task_id: str) -> None:
        content = self._dock_content()
        if content is not None:
            content.set_status(f"Coverage completed: {task_id}")
            content.append_debug(f"Coverage completed: {task_id}")

        if content is not None and content.should_download_coverage():
            self._download_and_save_coverage(task_id)
        else:
            self._add_coverage_wms_layer(task_id)

    def _on_coverage_failed(self, message: str) -> None:
        content = self._dock_content()
        if content is not None:
            content.set_status(message, is_error=True)
            content.append_debug(f"Coverage failed: {message}")

    def _on_debug_message(self, message: str) -> None:
        content = self._dock_content()
        if content is not None:
            content.append_debug(message)

    def _add_coverage_wms_layer(self, task_id: str) -> None:
        geoserver_base_url = PluginSettings.get_geoserver_base_url()
        if not geoserver_base_url:
            self._log_debug("No geoserver base URL could be derived from the API URL.")
            return

        wms_url = (
            f"url={geoserver_base_url}/wms"
            f"&layers=RF-SITE-PLANNER:{task_id}"
            f"&styles="
            f"&format=image/png"
            f"&crs=EPSG:3857"
            f"&contextualWMSLegend=0"
            f"&dpiMode=7"
        )
        self._log_debug(f"Attempting to add WMS layer with source: {wms_url}")
        layer = QgsRasterLayer(wms_url, f"Coverage {task_id}", "wms")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self._log_debug(f"WMS layer added to project: {task_id}")
            return

        content = self._dock_content()
        if content is not None:
            content.set_status(
                "Coverage finished, but the WMS layer could not be added.",
                is_error=True,
            )
            content.append_debug("WMS layer validation failed in QGIS.")
        self._log_debug(f"WMS layer validation failed for task {task_id}.")

    def _download_and_save_coverage(self, task_id: str) -> None:
        """Download coverage as GeoTIFF and save to radio-planning folder."""
        threading.Thread(
            target=self._download_coverage_worker,
            args=(task_id,),
            daemon=True,
        ).start()

    def _download_coverage_worker(self, task_id: str) -> None:
        """Worker thread for downloading coverage file."""
        import math
        from urllib.parse import urlparse
        
        try:
            content = self._dock_content()

            project = QgsProject.instance()
            project_path = project.fileName()

            if not project_path:
                if content is not None:
                    content.set_status("Cannot download: project not saved.", is_error=True)
                    content.append_debug("Project must be saved before downloading coverage.")
                return

            # Create radio-planning folder in the project directory
            project_dir = os.path.dirname(project_path)
            radio_planning_dir = os.path.join(project_dir, "radio-planning")
            os.makedirs(radio_planning_dir, exist_ok=True)
            
            coverage_file = os.path.join(radio_planning_dir, f"coverage_{task_id}.tif")
            
            # Get coverage parameters for bounding box calculation
            if content is None:
                return
                
            lat, lon = content.coverage_location()
            radius = content._coverage_radius.value()  # radius in km
            
            # Calculate bounding box from radius
            # Approximate: 1 degree ≈ 111 km
            radius_degrees = radius / 111.0
            lat_offset = radius_degrees
            lon_offset = radius_degrees / math.cos(math.radians(lat)) if abs(lat) < 85 else radius_degrees
            
            bbox_south = max(-90, lat - lat_offset)
            bbox_north = min(90, lat + lat_offset)
            bbox_west = max(-180, lon - lon_offset)
            bbox_east = min(180, lon + lon_offset)
            
            # Build WMS GetMap URL for GeoTIFF
            geoserver_base_url = PluginSettings.get_geoserver_base_url()
            if not geoserver_base_url:
                if content is not None:
                    content.append_debug("No geoserver base URL available for download.")
                return
            
            params = {
                "service": "WMS",
                "version": "1.1.0",
                "request": "GetMap",
                "layers": f"RF-SITE-PLANNER:{task_id}",
                "bbox": f"{bbox_west},{bbox_south},{bbox_east},{bbox_north}",
                "width": "768",
                "height": "534",
                "srs": "EPSG:4326",
                "styles": "",
                "format": "image/geotiff",
            }
            query_string = urlencode(params)
            wms_url = f"{geoserver_base_url}/RF-SITE-PLANNER/wms?{query_string}"
            
            content.append_debug(f"Downloading coverage from: {wms_url}")
            
            # Download with proper headers (to bypass WAF/edge layers)
            request = urllib.request.Request(url=wms_url, method="GET")
            parsed = urlparse(wms_url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            
            request.add_header(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            request.add_header("Accept", "*/*")
            request.add_header("Origin", origin)
            request.add_header("Referer", origin + "/")
            
            with urllib.request.urlopen(request, timeout=60) as response:
                with open(coverage_file, "wb") as f:
                    f.write(response.read())
            
            content.append_debug(f"Coverage saved to: {coverage_file}")
            
            # Add to QGIS with group
            self._add_downloaded_coverage_layer(coverage_file, task_id)
            
        except Exception as e:
            self._log_debug(f"Error downloading coverage: {e}")
            content = self._dock_content()
            if content is not None:
                content.set_status(f"Failed to download coverage: {e}", is_error=True)
                content.append_debug(f"Download error: {e}")

    def _add_downloaded_coverage_layer(self, file_path: str, task_id: str) -> None:
        """Add downloaded coverage to QGIS with Radio planning group."""
        try:
            project = QgsProject.instance()
            root = project.layerTreeRoot()
            
            # Find or create "Radio planning" group
            radio_group = None
            for child in root.children():
                if isinstance(child, QgsLayerTreeGroup) and child.name() == "Radio planning":
                    radio_group = child
                    break
            
            if radio_group is None:
                radio_group = root.insertGroup(0, "Radio planning")
            
            # Add raster layer
            layer = QgsRasterLayer(file_path, f"Coverage {task_id}", "gdal")
            if layer.isValid():
                project.addMapLayer(layer, addToLegend=False)
                radio_group.addLayer(layer)
                self._log_debug(f"Coverage layer added to 'Radio planning' group: {task_id}")
                
                content = self._dock_content()
                if content is not None:
                    content.set_status("Coverage downloaded and added to map.")
            else:
                self._log_debug(f"Downloaded coverage layer validation failed: {file_path}")
                
        except Exception as e:
            self._log_debug(f"Error adding downloaded layer: {e}")

    def _on_layer_will_be_removed(self, layer_ref) -> None:
        """When a layer from 'Radio planning' is removed, delete its file from disk."""
        project = QgsProject.instance()
        if isinstance(layer_ref, str):
            layer_id = layer_ref
            layer = project.mapLayer(layer_id)
        else:
            layer = layer_ref
            layer_id = layer.id() if layer is not None and hasattr(layer, "id") else ""

        if layer is None:
            return

        if not self._is_layer_in_radio_planning_group(layer_id):
            return

        source_path = self._local_path_from_layer_source(layer.source())
        if not source_path:
            return
        if not os.path.isfile(source_path):
            return
        radio_planning_dir = self._project_radio_planning_dir()
        if not radio_planning_dir:
            return
        if not self._is_path_in_directory(source_path, radio_planning_dir):
            return

        try:
            os.remove(source_path)
            self._log_debug(f"Deleted coverage file after layer removal: {source_path}")
        except Exception as error:
            self._log_debug(f"Could not delete coverage file '{source_path}': {error}")

    def _cleanup_orphan_radio_planning_files_on_startup(self) -> None:
        """Delete files from 'radio-planning' folder that are not present in Radio planning group."""
        project = QgsProject.instance()
        radio_planning_dir = self._project_radio_planning_dir()
        if not radio_planning_dir:
            return
        if not os.path.isdir(radio_planning_dir):
            return

        normalized_radio_planning_dir = os.path.normcase(os.path.abspath(radio_planning_dir))
        tracked_paths = set()
        in_use_paths = set()

        for layer in project.mapLayers().values():
            source_path = self._local_path_from_layer_source(layer.source())
            if source_path:
                in_use_paths.add(os.path.normcase(os.path.abspath(source_path)))

            layer_id = layer.id() if layer is not None and hasattr(layer, "id") else ""
            if not layer_id or not self._is_layer_in_radio_planning_group(layer_id):
                continue

            if not source_path:
                continue

            normalized_source = os.path.normcase(os.path.abspath(source_path))
            if os.path.dirname(normalized_source) == normalized_radio_planning_dir:
                tracked_paths.add(normalized_source)

        removed_count = 0
        for entry_name in os.listdir(radio_planning_dir):
            entry_path = os.path.join(radio_planning_dir, entry_name)
            if not os.path.isfile(entry_path):
                continue
            if not entry_name.lower().endswith((".tif", ".tiff")):
                continue

            normalized_entry = os.path.normcase(os.path.abspath(entry_path))
            if normalized_entry in tracked_paths:
                continue
            if normalized_entry in in_use_paths:
                self._log_debug(f"Startup cleanup skipped in-use file: {entry_path}")
                continue

            if self._delete_file_with_retry(entry_path):
                removed_count += 1

        if removed_count:
            self._log_debug(
                f"Startup cleanup finished: removed {removed_count} orphan file(s) from radio-planning."
            )

    def _delete_file_with_retry(self, path: str, retries: int = 3, delay_seconds: float = 0.4) -> bool:
        for attempt in range(1, retries + 1):
            try:
                os.remove(path)
                self._log_debug(f"Startup cleanup removed orphan coverage file: {path}")
                return True
            except PermissionError as error:
                # Windows file-lock race (e.g. scanner/indexer); retry a few times.
                win_error = getattr(error, "winerror", None)
                if win_error == 32 and attempt < retries:
                    time.sleep(delay_seconds)
                    continue
                self._log_debug(f"Startup cleanup could not remove '{path}': {error}")
                return False
            except Exception as error:
                self._log_debug(f"Startup cleanup could not remove '{path}': {error}")
                return False
        return False

    def _project_radio_planning_dir(self) -> str:
        project_path = QgsProject.instance().fileName()
        if not project_path:
            return ""
        return os.path.join(os.path.dirname(project_path), "radio-planning")

    def _is_path_in_directory(self, path: str, directory: str) -> bool:
        normalized_path = os.path.normcase(os.path.abspath(path))
        normalized_dir = os.path.normcase(os.path.abspath(directory))
        return os.path.dirname(normalized_path) == normalized_dir

    def _is_layer_in_radio_planning_group(self, layer_id: str) -> bool:
        root = QgsProject.instance().layerTreeRoot()
        layer_node = root.findLayer(layer_id)
        if layer_node is None:
            return False

        parent = layer_node.parent()
        while parent is not None:
            if isinstance(parent, QgsLayerTreeGroup) and parent.name() == "Radio planning":
                return True
            parent = parent.parent()
        return False

    def _local_path_from_layer_source(self, source: str) -> str:
        if not source:
            return ""
        source_path = source.split("|", 1)[0].strip().strip('"').strip("'")
        if source_path.lower().startswith("file://"):
            source_path = source_path[7:]
        return source_path

    def _dock_content(self):
        if self.dock_widget is None:
            return None
        return self.dock_widget.widget()

    def _ensure_dock_widget(self):
        if self.dock_widget is not None:
            return

        self.dock_widget = QDockWidget("RF Planner", self.iface.mainWindow())
        self.dock_widget.setObjectName("RFPlannerDock")

        content = DockWidget(self.dock_widget)
        content.requestSettings.connect(self._save_api_url_from_dock)
        content.testConnectionRequested.connect(self.api_client.test_connection)
        content.apiUrlChanged.connect(PluginSettings.set_api_url)
        content.pickCoordinatesRequested.connect(self._start_coordinate_pick)
        content.runCoverageRequested.connect(self.run_coverage)
        content.saveParametersRequested.connect(self._save_coverage_parameters)
        content.loadParametersRequested.connect(self._load_coverage_parameters)
        content.saveScenarioRequested.connect(self._save_scenario)
        content.loadScenarioRequested.connect(self._load_scenario)
        content.deleteScenarioRequested.connect(self._delete_scenario)
        content.set_api_url(PluginSettings.get_api_url())
        if not PluginSettings.get_api_url():
            content.set_status("Set API base URL and click Save.", is_error=True)
        self.dock_widget.setWidget(content)
        self.dock_widget.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widget)

        self._refresh_scenarios()

        if self._restore_last_scenario():
            content.append_debug("Loaded last active scenario for this project.")

        saved_params = PluginSettings.get_coverage_parameters()
        if saved_params and not content.current_scenario_name():
            content.set_coverage_parameters(saved_params)
            content.append_debug("Loaded saved coverage parameters.")

    def _restore_previous_map_tool(self):
        canvas = self.iface.mapCanvas()
        if self._previous_map_tool is not None:
            canvas.setMapTool(self._previous_map_tool)
            self._previous_map_tool = None

    def _log_debug(self, message: str) -> None:
        QgsMessageLog.logMessage(message, "RF Planner", Qgis.MessageLevel.Info)
        content = self._dock_content()
        if content is not None and hasattr(content, "append_debug"):
            content.append_debug(message)

    def _save_coverage_parameters(self, params: dict) -> None:
        content = self._dock_content()
        PluginSettings.set_coverage_parameters(params)
        scenario_name = content.current_scenario_name() if content is not None else ""
        if scenario_name:
            try:
                PluginSettings.save_scenario(scenario_name, params)
                self._refresh_scenarios(selected=scenario_name)
            except ValueError as error:
                if content is not None:
                    content.set_status(str(error), is_error=True)
                    content.append_debug(f"Scenario save failed: {error}")
                return
        if content is not None:
            content.set_status("Coverage parameters saved.")
            content.append_debug("Coverage parameters saved to QGIS settings.")

    def _load_coverage_parameters(self) -> None:
        content = self._dock_content()
        if content is None:
            return

        params = PluginSettings.get_coverage_parameters()
        if not params:
            content.set_status("No saved coverage parameters found.", is_error=True)
            content.append_debug("Load parameters requested, but no saved data exists.")
            return

        content.set_coverage_parameters(params)
        content.set_status("Coverage parameters loaded.")
        content.append_debug("Coverage parameters loaded from QGIS settings.")

    def _save_scenario(self, scenario_name: str, params: object) -> None:
        content = self._dock_content()
        name = PluginSettings.normalize_scenario_name(scenario_name)
        if not name:
            if content is not None:
                content.set_status("Scenario name is empty.", is_error=True)
                content.append_debug("Scenario save aborted: empty name.")
            return

        try:
            PluginSettings.save_scenario(name, dict(params))
            self._refresh_scenarios(selected=name)
            if content is not None:
                content.set_current_scenario_name(name)
                content.set_status(f"Scenario saved: {name}")
                content.append_debug(f"Scenario saved: {name}")
        except ValueError as error:
            if content is not None:
                content.set_status(str(error), is_error=True)
                content.append_debug(f"Scenario save failed: {error}")

    def _load_scenario(self, scenario_name: str) -> None:
        content = self._dock_content()
        name = PluginSettings.normalize_scenario_name(scenario_name)
        if not name:
            if content is not None:
                content.set_status("Select a scenario to load.", is_error=True)
            return

        params = PluginSettings.get_scenario(name)
        if not params:
            if content is not None:
                content.set_status(f"Scenario not found: {name}", is_error=True)
                content.append_debug(f"Load failed: scenario not found ({name})")
            return

        if content is not None:
            content.set_coverage_parameters(params)
            content.set_current_scenario_name(name)
            content.set_status(f"Scenario loaded: {name}")
            content.append_debug(f"Scenario loaded: {name}")
        PluginSettings.set_last_scenario_name(name)

    def _delete_scenario(self, scenario_name: str) -> None:
        content = self._dock_content()
        name = PluginSettings.normalize_scenario_name(scenario_name)
        if not name:
            if content is not None:
                content.set_status("Select a scenario to delete.", is_error=True)
            return

        PluginSettings.delete_scenario(name)
        self._refresh_scenarios(selected="")
        if content is not None:
            content.set_scenario_dirty(False)
            content.set_status(f"Scenario deleted: {name}")
            content.append_debug(f"Scenario deleted: {name}")

    def _refresh_scenarios(self, selected: str = "") -> None:
        content = self._dock_content()
        if content is None:
            return

        scenario_names = PluginSettings.list_scenarios()
        last = selected.strip() or PluginSettings.get_last_scenario_name()
        content.set_scenario_names(scenario_names, selected=last)
        if last and last in scenario_names:
            PluginSettings.set_last_scenario_name(last)

    def _restore_last_scenario(self) -> bool:
        content = self._dock_content()
        if content is None:
            return False

        last = PluginSettings.get_last_scenario_name().strip()
        if not last:
            return False

        params = PluginSettings.get_scenario(last)
        if not params:
            return False

        content.set_coverage_parameters(params)
        content.set_current_scenario_name(last)
        return True

