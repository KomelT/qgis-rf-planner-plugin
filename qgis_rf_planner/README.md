# RF Planner QGIS Plugin

Native PyQt/QGIS plugin scaffold for RF site planning.
Targeted at QGIS 4.0.

## Current state

- Right-side dock widget shell
- First-launch API URL setup
- Persistent API URL storage in QSettings
- API connectivity check using Qt networking

## Development target

The plugin is intentionally native. It does not embed the Vue app.
The Vue app in `rf-site-planner/` is kept as a reference for behavior and layout only.

## Suggested QGIS development loop

1. Copy or symlink `qgis_rf_planner/` into your QGIS plugin directory.
2. Enable the plugin in QGIS.
3. Use the dock widget action to open the panel.
4. Enter the API URL and test connectivity.
5. Extend the dock with coverage and LOS controls.
