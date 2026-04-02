"""Dialog for configuring RF Planner plugin settings."""

from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from .settings import PluginSettings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RF Planner Settings")
        self.setMinimumWidth(520)

        self._api_url = QLineEdit(self)
        self._api_url.setPlaceholderText("https://rf-planner.komelt.dev/api/")
        self._api_url.setText(PluginSettings.get_api_url())

        help_text = QLabel(
            "Enter the base URL of the RF Planner API. The plugin uses this value for all backend requests."
        )
        help_text.setWordWrap(True)

        form = QFormLayout()
        form.addRow("API base URL", self._api_url)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(help_text)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def api_url(self) -> str:
        return self._api_url.text().strip()
