# QGIS RF Planner Plugin

This repository is the workspace for the QGIS desktop plugin frontend for RF site planning.

The `rf-site-planner/` submodule is kept here as a reference implementation of the existing web app and backend contract. The plugin itself should not reimplement the backend. It should connect to the API over HTTP and provide a QGIS-native workflow around it.

## Goal

- Right-side QGIS dock widget that feels similar to the current Vue sidebar.
- First-launch API setup, where the user enters the backend URL, for example `https://rf-planner.komelt.dev/api/`.
- Pure frontend plugin logic: request payloads, task polling, layer/result rendering, and project interaction live in QGIS.
- Backend stays external and can evolve independently.

## Recommended Shape

1. Build a QGIS plugin with a dock widget on the right side.
2. Persist the API base URL in QGIS settings after the first launch.
3. Reuse the Vue app as a UI reference, but keep the QGIS plugin as the source of truth for the desktop workflow.
4. Start with the smallest visible slice: connect settings, a sidebar shell, and one API action.

## Fastest Way To See Progress In QGIS

The quickest development loop is:

- Install the plugin into the QGIS user plugin directory via a symlink or a copy.
- Use QGIS Plugin Reloader during development so changes can be reloaded without a full restart.
- Keep the first iteration minimal: a dock widget, API settings dialog, and one button that calls the backend.
- If UI parity with the Vue app matters more than native widgets at the start, embed the existing frontend in a `QWebEngineView` inside the dock widget and then replace pieces gradually with native PyQt widgets.

## QGIS 4.0 Compatibility

The plugin should be written with forward compatibility in mind:

- Prefer `PyQt6`-compatible patterns.
- Use `qgis.PyQt` imports instead of direct Qt bindings where possible.
- Avoid deprecated QGIS APIs and old-style Qt patterns that are likely to break across major versions.
- The plugin is now targeted at QGIS 4.0. Older 3.x builds are no longer the primary compatibility target.

## Suggested First Milestones

- Create the plugin scaffold and load it in QGIS.
- Add the API URL settings dialog.
- Add the right dock sidebar with the same information architecture as the Vue app.
- Add a working coverage or LOS request flow.
- Render results back into QGIS as layers or overlays.

## Native Plugin Scaffold

The native QGIS plugin now lives in [`qgis_rf_planner/`](qgis_rf_planner). It is a pure PyQt/QGIS implementation, with no embedded Vue runtime.

To test it quickly in QGIS, symlink or copy the folder into your QGIS plugin directory, then enable the plugin from the Plugin Manager. The first run will prompt for the API URL, and the dock widget will appear on the right side once opened.

## Development Reference

- Vue app reference: [`rf-site-planner/app`](rf-site-planner/app)
- API reference: [`rf-site-planner/api`](rf-site-planner/api)
- Existing app documentation: [`rf-site-planner/README.md`](rf-site-planner/README.md)
