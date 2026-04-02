# QGIS RF Planner Plugin

This repository is the workspace for the QGIS desktop plugin frontend for RF site planning.

![RF Planner Plugin Screenshot](assets/rf-planner-screenshot.png)

## Goal

- Right-side QGIS dock widget that feels similar to the current Vue sidebar.
- First-launch API setup, where the user enters the backend URL, for example `https://rf-planner.komelt.dev/api/`.
- Pure frontend plugin logic: request payloads, task polling, layer/result rendering, and project interaction live in QGIS.
- Backend stays external and can evolve independently.

## Current Plugin Features

- Native QGIS 4 plugin panel that auto-docks to the right side.
- Project-scoped named scenarios for saving and loading multiple coverage setups.
- Coverage UI organized in sections: Transmitter, Receiver, Environment, and Output.
- `Pick on map` coordinate pipette directly in the Transmitter section.
- Inline API base URL save/test in the panel (no popup settings workflow).
- Coverage parameter persistence with `Save parameters` and `Load parameters`.
- Large resizable debug panel for request/response traces and status messages.
- Coverage task flow: submit -> poll task status -> add generated WMS layer to QGIS.
- Plugin icon integrated for plugin manager and plugin repository metadata.

## 5G Roadmap

The idea is to build this in stages so each step becomes useful on its own and unlocks the next one.

### Step 1: Core Planning Workspace

Goal: make the plugin a solid shell for planning work.

- Keep the right-docked panel and parameter saving/loading.
- Add project and scenario presets.
- Support multiple coverage runs per project.
- Make the debug and status feedback reliable.

### Step 2: 5G Site and Sector Inputs

Goal: model real 5G transmitters instead of a single generic point.

- Add 5G band presets like n28, n41, n78, and n1.
- Add frequency, bandwidth, and duplex mode inputs.
- Add antenna azimuth, tilt, beamwidth, and sector gain.
- Support one site with multiple sectors.

### Step 3: 5G Coverage Outputs

Goal: make the maps useful for radio engineering decisions.

- Add RSRP output maps.
- Add SINR and RSRQ outputs.
- Add best-server maps and overlap detection.
- Add weak-coverage and hole detection layers.

### Step 4: Capacity and Planning Helpers

Goal: move from coverage-only to planning-aware decisions.

- Add user density and traffic demand inputs.
- Add rough sector capacity estimates.
- Add scenario comparison tools.
- Add threshold-based warnings for undersized sites.

### Step 5: Import and Export

Goal: make it easy to work with real network planning data.

- Import site lists from CSV or GeoJSON.
- Export planned sectors and coverage results.
- Save named scenarios for later reuse.
- Support sharing plans between projects.

### Step 6: Advanced Planning

Goal: improve realism and workflow quality once the basics are stable.

- Add urban / suburban / rural presets.
- Add clutter and building assumptions.
- Add indoor/outdoor planning modes.
- Add batch comparisons for multiple candidate sites.

## Install Options

### Option 1: Plugin Repository (recommended for users)

Use this when you want updates through QGIS Plugin Manager from your hosted `plugins.xml`.

1. Host [plugins.xml](plugins.xml) and release ZIP files at stable URLs.
2. In QGIS, open `Plugins -> Manage and Install Plugins... -> Settings`.
3. Add a new repository URL pointing to your hosted `plugins.xml`.
4. Search for `RF Planner` and install/update from the repository list.

### Option 2: Install From ZIP

Use this when you want a simple offline or one-time install.

1. Download the latest plugin ZIP release asset (for example `qgis_rf_planner-vX.Y.Z.zip`).
2. In QGIS, open `Plugins -> Manage and Install Plugins...`.
3. Choose `Install from ZIP`.
4. Select the downloaded ZIP file and install.

## Development Reference

The `rf-site-planner/` submodule is kept here as a reference implementation of the existing web app and backend contract. The plugin itself should not reimplement the backend. It should connect to the API over HTTP and provide a QGIS-native workflow around it.

- Vue app reference: [`rf-site-planner/app`](rf-site-planner/app)
- API reference: [`rf-site-planner/api`](rf-site-planner/api)
- Existing app documentation: [`rf-site-planner/README.md`](rf-site-planner/README.md)
