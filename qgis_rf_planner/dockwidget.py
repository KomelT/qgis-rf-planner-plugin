"""Native dock widget for the RF Planner plugin."""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QComboBox,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class DockWidget(QWidget):
    requestSettings = pyqtSignal(str)
    testConnectionRequested = pyqtSignal(str)
    apiUrlChanged = pyqtSignal(str)
    runCoverageRequested = pyqtSignal()
    pickCoordinatesRequested = pyqtSignal()
    saveParametersRequested = pyqtSignal(dict)
    loadParametersRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RFPlannerDockWidget")

        self._api_url = QLineEdit(self)
        self._api_url.setPlaceholderText("https://rf-planner.komelt.dev/api/")
        self._api_url.textChanged.connect(self.apiUrlChanged.emit)

        self._status_label = QLabel("Set the API URL to start.", self)
        self._status_label.setWordWrap(True)

        self._debug_log = QPlainTextEdit(self)
        self._debug_log.setReadOnly(True)
        self._debug_log.setPlaceholderText("Request debug output will appear here.")
        self._debug_log.setMinimumHeight(80)

        self._coverage_lat = self._spin_box(-90.0, 90.0, 6, 45.85473269336)
        self._coverage_lon = self._spin_box(-180.0, 180.0, 6, 13.72616645611)
        self._coverage_tx_height = self._spin_box(1.0, 1000.0, 2, 2.0)
        self._coverage_tx_power = self._spin_box(1.0, 100.0, 2, 27.0)
        self._coverage_tx_gain = self._spin_box(0.0, 50.0, 2, 5.0)
        self._coverage_tx_loss = self._spin_box(0.0, 100.0, 2, 2.0)
        self._coverage_rx_height = self._spin_box(1.0, 100.0, 2, 2.0)
        self._coverage_rx_loss = self._spin_box(0.0, 100.0, 2, 2.0)
        self._coverage_radius = self._spin_box(1.0, 500.0, 1, 30.0)
        self._coverage_frequency = self._spin_box(20.0, 30000.0, 1, 868.5)
        self._coverage_colormap = QComboBox(self)
        self._coverage_colormap.addItems(["plasma", "viridis", "turbo", "jet", "hot"])
        self._coverage_colormap.setCurrentText("plasma")

        self._coverage_clutter_height = self._spin_box(0.0, 100.0, 2, 0.9)
        self._coverage_ground_dielectric = self._spin_box(1.0, 100.0, 3, 15.0)
        self._coverage_ground_conductivity = self._spin_box(0.0, 10.0, 6, 0.005)
        self._coverage_atmosphere_bending = self._spin_box(0.0, 1000.0, 2, 301.0)
        self._coverage_situation_fraction = self._spin_box(1.0, 100.0, 1, 95.0)
        self._coverage_time_fraction = self._spin_box(1.0, 100.0, 1, 95.0)

        self._coverage_radio_climate = QComboBox(self)
        self._coverage_radio_climate.addItems(
            [
                "equatorial",
                "continental_subtropical",
                "maritime_subtropical",
                "desert",
                "continental_temperate",
                "maritime_temperate_land",
                "maritime_temperate_sea",
            ]
        )
        self._coverage_radio_climate.setCurrentText("continental_temperate")

        self._coverage_polarization = QComboBox(self)
        self._coverage_polarization.addItems(["vertical", "horizontal"])
        self._coverage_polarization.setCurrentText("vertical")

        self._coverage_min_dbm = self._spin_box(-200.0, 0.0, 1, -153.0)
        self._coverage_max_dbm = self._spin_box(-200.0, 0.0, 1, -80.0)

        self._coverage_high_resolution = QCheckBox("High resolution terrain", self)
        self._coverage_high_resolution.setChecked(False)
        self._coverage_itm_mode = QCheckBox("Use ITM mode", self)
        self._coverage_itm_mode.setChecked(True)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        main_splitter = QSplitter(self)
        main_splitter.setOrientation(Qt.Orientation.Vertical)
        main_splitter.setChildrenCollapsible(False)
        root.addWidget(main_splitter)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("RF Planner", content)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")

        subtitle = QLabel(
            "Native QGIS workspace for radio planning, connected to a remote API.",
            content,
        )
        subtitle.setWordWrap(True)

        api_card = self._card(content)
        api_layout = QVBoxLayout(api_card)
        api_layout.setSpacing(8)
        api_layout.addWidget(QLabel("API base URL", api_card))
        api_layout.addWidget(self._api_url)

        button_row = QHBoxLayout()
        self._save_button = QPushButton("Save", api_card)
        self._test_button = QPushButton("Test connection", api_card)
        self._save_button.clicked.connect(
            lambda: self.requestSettings.emit(self._api_url.text().strip())
        )
        self._test_button.clicked.connect(
            lambda: self.testConnectionRequested.emit(self._api_url.text().strip())
        )
        button_row.addWidget(self._save_button)
        button_row.addWidget(self._test_button)
        api_layout.addLayout(button_row)
        api_layout.addWidget(self._status_label)

        coverage_card = self._card(content)
        coverage_layout = QVBoxLayout(coverage_card)
        coverage_layout.setSpacing(10)
        coverage_layout.addWidget(QLabel("Coverage", coverage_card))

        transmitter_group = self._section("Transmitter", coverage_card)
        transmitter_form = self._section_form(transmitter_group)
        transmitter_form.addRow("Latitude", self._coverage_lat)
        transmitter_form.addRow("Longitude", self._coverage_lon)

        self._coverage_pick_button = QPushButton("Pick on map", transmitter_group)
        self._coverage_pick_button.clicked.connect(self.pickCoordinatesRequested.emit)
        transmitter_form.addRow(self._coverage_pick_button)

        transmitter_form.addRow("TX height (m)", self._coverage_tx_height)
        transmitter_form.addRow("TX power (dBm)", self._coverage_tx_power)
        transmitter_form.addRow("TX gain (dB)", self._coverage_tx_gain)
        transmitter_form.addRow("TX loss (dB)", self._coverage_tx_loss)

        receiver_group = self._section("Receiver", coverage_card)
        receiver_form = self._section_form(receiver_group)
        receiver_form.addRow("RX height (m)", self._coverage_rx_height)
        receiver_form.addRow("RX loss (dB)", self._coverage_rx_loss)

        environment_group = self._section("Environment", coverage_card)
        environment_form = self._section_form(environment_group)
        environment_form.addRow("Clutter height (m)", self._coverage_clutter_height)
        environment_form.addRow("Ground dielectric", self._coverage_ground_dielectric)
        environment_form.addRow("Ground conductivity", self._coverage_ground_conductivity)
        environment_form.addRow("Atmosphere bending", self._coverage_atmosphere_bending)
        environment_form.addRow("Radio climate", self._coverage_radio_climate)
        environment_form.addRow("Polarization", self._coverage_polarization)
        environment_form.addRow("Situation fraction (%)", self._coverage_situation_fraction)
        environment_form.addRow("Time fraction (%)", self._coverage_time_fraction)

        output_group = self._section("Output", coverage_card)
        output_form = self._section_form(output_group)
        output_form.addRow("Radius (km)", self._coverage_radius)
        output_form.addRow("Frequency (MHz)", self._coverage_frequency)
        output_form.addRow("Colormap", self._coverage_colormap)
        output_form.addRow("Min dBm", self._coverage_min_dbm)
        output_form.addRow("Max dBm", self._coverage_max_dbm)
        output_form.addRow(self._coverage_high_resolution)
        output_form.addRow(self._coverage_itm_mode)

        coverage_layout.addWidget(transmitter_group)
        coverage_layout.addWidget(receiver_group)
        coverage_layout.addWidget(environment_group)
        coverage_layout.addWidget(output_group)

        coverage_button_row = QHBoxLayout()
        self._coverage_run_button = QPushButton("Run coverage", coverage_card)
        self._coverage_run_button.clicked.connect(self.runCoverageRequested.emit)
        coverage_button_row.addWidget(self._coverage_run_button)
        coverage_layout.addLayout(coverage_button_row)

        params_button_row = QHBoxLayout()
        self._save_params_button = QPushButton("Save parameters", coverage_card)
        self._load_params_button = QPushButton("Load parameters", coverage_card)
        self._save_params_button.clicked.connect(
            lambda: self.saveParametersRequested.emit(self.coverage_parameters())
        )
        self._load_params_button.clicked.connect(self.loadParametersRequested.emit)
        params_button_row.addWidget(self._save_params_button)
        params_button_row.addWidget(self._load_params_button)
        coverage_layout.addLayout(params_button_row)

        content_layout.addWidget(title)
        content_layout.addWidget(subtitle)
        content_layout.addWidget(api_card)
        content_layout.addWidget(coverage_card)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        main_splitter.addWidget(scroll)

        debug_panel = self._card(self)
        debug_layout = QVBoxLayout(debug_panel)
        debug_layout.setContentsMargins(8, 8, 8, 8)
        debug_layout.setSpacing(6)
        debug_layout.addWidget(QLabel("Debug log", debug_panel))
        debug_layout.addWidget(self._debug_log)
        main_splitter.addWidget(debug_panel)
        main_splitter.setSizes([760, 200])

    def _card(self, parent: QWidget) -> QFrame:
        card = QFrame(parent)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            """
            QFrame {
                border: 1px solid rgba(127, 127, 127, 0.35);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.03);
            }
            """
        )
        return card

    def _section(self, title: str, parent: QWidget) -> QGroupBox:
        group = QGroupBox(title, parent)
        return group

    def _section_form(self, group: QGroupBox) -> QFormLayout:
        form = QFormLayout(group)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)
        return form

    def _spin_box(self, minimum: float, maximum: float, decimals: int, value: float) -> QDoubleSpinBox:
        spin_box = QDoubleSpinBox(self)
        spin_box.setRange(minimum, maximum)
        spin_box.setDecimals(decimals)
        spin_box.setSingleStep(1 if decimals == 0 else 0.5)
        spin_box.setValue(value)
        return spin_box

    def _row(self, label: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(label, self))
        row.addWidget(widget)
        return row

    def set_api_url(self, api_url: str) -> None:
        self._api_url.setText(api_url)

    def api_url(self) -> str:
        return self._api_url.text().strip()

    def coverage_location(self) -> tuple[float, float]:
        return self._coverage_lat.value(), self._coverage_lon.value()

    def set_coverage_location(self, latitude: float, longitude: float) -> None:
        self._coverage_lat.setValue(latitude)
        self._coverage_lon.setValue(longitude)

    def coverage_payload_defaults(self) -> dict:
        return {
            "tx_height": self._coverage_tx_height.value(),
            "tx_power": self._coverage_tx_power.value(),
            "tx_gain": self._coverage_tx_gain.value(),
            "tx_loss": self._coverage_tx_loss.value(),
            "frequency_mhz": self._coverage_frequency.value(),
            "rx_height": self._coverage_rx_height.value(),
            "rx_loss": self._coverage_rx_loss.value(),
            "clutter_height": self._coverage_clutter_height.value(),
            "ground_dielectric": self._coverage_ground_dielectric.value(),
            "ground_conductivity": self._coverage_ground_conductivity.value(),
            "atmosphere_bending": self._coverage_atmosphere_bending.value(),
            "radio_climate": self._coverage_radio_climate.currentText(),
            "polarization": self._coverage_polarization.currentText(),
            "radius": self._coverage_radius.value(),
            "situation_fraction": self._coverage_situation_fraction.value(),
            "time_fraction": self._coverage_time_fraction.value(),
            "high_resolution": self._coverage_high_resolution.isChecked(),
            "colormap": self._coverage_colormap.currentText(),
            "min_dbm": self._coverage_min_dbm.value(),
            "max_dbm": self._coverage_max_dbm.value(),
            "itm_mode": self._coverage_itm_mode.isChecked(),
        }

    def coverage_parameters(self) -> dict:
        data = self.coverage_payload_defaults()
        lat, lon = self.coverage_location()
        data["lat"] = lat
        data["lon"] = lon
        return data

    def set_coverage_parameters(self, params: dict) -> None:
        if not params:
            return

        self._coverage_lat.setValue(float(params.get("lat", self._coverage_lat.value())))
        self._coverage_lon.setValue(float(params.get("lon", self._coverage_lon.value())))
        self._coverage_tx_height.setValue(float(params.get("tx_height", self._coverage_tx_height.value())))
        self._coverage_tx_power.setValue(float(params.get("tx_power", self._coverage_tx_power.value())))
        self._coverage_tx_gain.setValue(float(params.get("tx_gain", self._coverage_tx_gain.value())))
        self._coverage_tx_loss.setValue(float(params.get("tx_loss", self._coverage_tx_loss.value())))
        self._coverage_frequency.setValue(float(params.get("frequency_mhz", self._coverage_frequency.value())))
        self._coverage_rx_height.setValue(float(params.get("rx_height", self._coverage_rx_height.value())))
        self._coverage_rx_loss.setValue(float(params.get("rx_loss", self._coverage_rx_loss.value())))
        self._coverage_clutter_height.setValue(float(params.get("clutter_height", self._coverage_clutter_height.value())))
        self._coverage_ground_dielectric.setValue(float(params.get("ground_dielectric", self._coverage_ground_dielectric.value())))
        self._coverage_ground_conductivity.setValue(float(params.get("ground_conductivity", self._coverage_ground_conductivity.value())))
        self._coverage_atmosphere_bending.setValue(float(params.get("atmosphere_bending", self._coverage_atmosphere_bending.value())))
        self._coverage_situation_fraction.setValue(float(params.get("situation_fraction", self._coverage_situation_fraction.value())))
        self._coverage_time_fraction.setValue(float(params.get("time_fraction", self._coverage_time_fraction.value())))
        self._coverage_radius.setValue(float(params.get("radius", self._coverage_radius.value())))
        self._coverage_min_dbm.setValue(float(params.get("min_dbm", self._coverage_min_dbm.value())))
        self._coverage_max_dbm.setValue(float(params.get("max_dbm", self._coverage_max_dbm.value())))

        colormap = str(params.get("colormap", self._coverage_colormap.currentText()))
        radio_climate = str(params.get("radio_climate", self._coverage_radio_climate.currentText()))
        polarization = str(params.get("polarization", self._coverage_polarization.currentText()))

        if self._coverage_colormap.findText(colormap) >= 0:
            self._coverage_colormap.setCurrentText(colormap)
        if self._coverage_radio_climate.findText(radio_climate) >= 0:
            self._coverage_radio_climate.setCurrentText(radio_climate)
        if self._coverage_polarization.findText(polarization) >= 0:
            self._coverage_polarization.setCurrentText(polarization)

        self._coverage_high_resolution.setChecked(bool(params.get("high_resolution", self._coverage_high_resolution.isChecked())))
        self._coverage_itm_mode.setChecked(bool(params.get("itm_mode", self._coverage_itm_mode.isChecked())))

    def set_status(self, message: str, is_error: bool = False) -> None:
        color = "#f87171" if is_error else "#86efac"
        self._status_label.setStyleSheet(f"color: {color};")
        self._status_label.setText(message)

    def append_debug(self, message: str) -> None:
        self._debug_log.appendPlainText(message)
