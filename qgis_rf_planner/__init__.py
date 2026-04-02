"""RF Planner QGIS plugin package."""

from .rf_planner_plugin import RFPlannerPlugin


def classFactory(iface):
    return RFPlannerPlugin(iface)
