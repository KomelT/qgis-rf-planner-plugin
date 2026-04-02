"""Main QGIS plugin entry point for RF Planner."""

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

        self.api_client.connectionSucceeded.connect(self._on_connection_success)
        self.api_client.connectionFailed.connect(self._on_connection_failed)
        self.api_client.coverageSubmitted.connect(self._on_coverage_submitted)
        self.api_client.coverageCompleted.connect(self._on_coverage_completed)
        self.api_client.coverageFailed.connect(self._on_coverage_failed)
        self.api_client.debugMessage.connect(self._on_debug_message)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu("RF Planner", self.action)
            self.iface.removeToolBarIcon(self.action)
        if self.dock_widget is not None:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

    def show_dock_widget(self):
        if self.dock_widget is None:
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
            content.set_api_url(PluginSettings.get_api_url())
            if not PluginSettings.get_api_url():
                content.set_status("Set API base URL and click Save.", is_error=True)

            saved_params = PluginSettings.get_coverage_parameters()
            if saved_params:
                content.set_coverage_parameters(saved_params)
                content.append_debug("Loaded saved coverage parameters.")

            self.dock_widget.setWidget(content)
            self.dock_widget.setAllowedAreas(
                Qt.DockWidgetArea.LeftDockWidgetArea
                | Qt.DockWidgetArea.RightDockWidgetArea
            )
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widget)

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

    def _dock_content(self):
        if self.dock_widget is None:
            return None
        return self.dock_widget.widget()

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
