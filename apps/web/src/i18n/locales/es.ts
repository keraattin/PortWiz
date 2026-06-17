import type { TKey } from "./en";

export const es: Partial<Record<TKey, string>> = {
  // Navigation
  "nav.dashboard": "Panel",
  "nav.inventory": "Inventario",
  "nav.assets": "Activos",
  "nav.vlans": "VLAN",
  "nav.scanning": "Escaneo",
  "nav.scans": "Escaneos",
  "nav.agents": "Agentes",
  "nav.changes": "Cambios",
  "nav.tasks": "Tareas",
  "nav.compliance": "Cumplimiento",
  "nav.assistant": "Asistente",
  "nav.admin": "Administración",
  "nav.users": "Usuarios",
  "nav.settings": "Ajustes",

  // Header / chrome
  "chrome.signOut": "Cerrar sesión",
  "chrome.switchToLight": "Cambiar al modo claro",
  "chrome.switchToDark": "Cambiar al modo oscuro",
  "chrome.language": "Idioma",

  // Common actions / labels
  "common.add": "Añadir",
  "common.save": "Guardar",
  "common.saving": "Guardando…",
  "common.cancel": "Cancelar",
  "common.delete": "Eliminar",
  "common.create": "Crear",
  "common.run": "Ejecutar",
  "common.test": "Probar",
  "common.close": "Cerrar",
  "common.edit": "Editar",
  "common.loading": "Cargando…",
  "common.noData": "Aún no hay datos",
  "common.error": "Algo salió mal",

  // Dashboard
  "dashboard.apiStatus": "Estado de la API:",
  "dashboard.checking": "comprobando…",
  "dashboard.healthy": "operativa",
  "dashboard.unreachable": "inaccesible",
  "dashboard.metric.assets": "Activos",
  "dashboard.metric.vlans": "VLAN",
  "dashboard.metric.agentsOnline": "Agentes en línea",
  "dashboard.metric.openChanges": "Cambios abiertos",
  "dashboard.metric.openTasks": "Tareas abiertas",
  "dashboard.metric.pendingRuns": "Escaneos pendientes",
  "dashboard.scanWaiting": "{count} escaneo(s) pendiente(s), pero ningún agente en línea.",
  "dashboard.checkAgents": "Revisa tus agentes",
  "dashboard.gettingStarted": "Primeros pasos",
  "dashboard.gettingStartedHint":
    "Sigue estos pasos para pasar de una instalación vacía a la detección confirmada de cambios.",
  "dashboard.step.addVlan": "Añadir una VLAN",
  "dashboard.step.addAssets": "Añadir activos para escanear",
  "dashboard.step.enrollAgent": "Registrar un agente de escaneo",
  "dashboard.step.createScan": "Crear un perfil de escaneo y ejecutarlo",
  "dashboard.step.reviewChanges": "Revisar los cambios confirmados",
  "dashboard.enrolledNoneOnline": "registrado, pero ninguno en línea",
  "dashboard.lastScan": "Último escaneo: {when}",

  // Dashboard charts
  "trends.title": "Tendencias",
  "trends.changes30d": "Cambios confirmados (últimos 30 días)",
  "trends.changes30dHint": "Recuento diario de cambios confirmados de puertos y servicios.",
  "trends.assetsByCriticality": "Activos por criticidad",
  "trends.complianceStatus": "Estado de cumplimiento",
  "trends.runsByStatus": "Escaneos por estado",
  "trends.changesByType": "Cambios por tipo",
};
