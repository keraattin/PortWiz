import type { TKey } from "./en";

export const de: Partial<Record<TKey, string>> = {
  // Navigation
  "nav.dashboard": "Übersicht",
  "nav.inventory": "Inventar",
  "nav.assets": "Assets",
  "nav.vlans": "VLANs",
  "nav.scanning": "Scannen",
  "nav.scans": "Scans",
  "nav.agents": "Agenten",
  "nav.changes": "Änderungen",
  "nav.tasks": "Aufgaben",
  "nav.compliance": "Compliance",
  "nav.assistant": "Assistent",
  "nav.admin": "Verwaltung",
  "nav.users": "Benutzer",
  "nav.settings": "Einstellungen",

  // Header / chrome
  "chrome.signOut": "Abmelden",
  "chrome.switchToLight": "Zum hellen Modus wechseln",
  "chrome.switchToDark": "Zum dunklen Modus wechseln",
  "chrome.language": "Sprache",

  // Common actions / labels
  "common.add": "Hinzufügen",
  "common.save": "Speichern",
  "common.saving": "Wird gespeichert…",
  "common.cancel": "Abbrechen",
  "common.delete": "Löschen",
  "common.create": "Erstellen",
  "common.run": "Ausführen",
  "common.test": "Testen",
  "common.close": "Schließen",
  "common.edit": "Bearbeiten",
  "common.loading": "Wird geladen…",
  "common.noData": "Noch keine Daten",
  "common.error": "Etwas ist schiefgelaufen",

  // Dashboard
  "dashboard.apiStatus": "API-Status:",
  "dashboard.checking": "wird geprüft…",
  "dashboard.healthy": "gesund",
  "dashboard.unreachable": "nicht erreichbar",
  "dashboard.metric.assets": "Assets",
  "dashboard.metric.vlans": "VLANs",
  "dashboard.metric.agentsOnline": "Agenten online",
  "dashboard.metric.openChanges": "Offene Änderungen",
  "dashboard.metric.openTasks": "Offene Aufgaben",
  "dashboard.metric.pendingRuns": "Ausstehende Scans",
  "dashboard.scanWaiting": "{count} ausstehende Scans, aber kein Agent online.",
  "dashboard.checkAgents": "Agenten prüfen",
  "dashboard.gettingStarted": "Erste Schritte",
  "dashboard.gettingStartedHint":
    "Folgen Sie diesen Schritten, um von einer leeren Installation zur bestätigten Änderungserkennung zu gelangen.",
  "dashboard.step.addVlan": "Ein VLAN hinzufügen",
  "dashboard.step.addAssets": "Zu scannende Assets hinzufügen",
  "dashboard.step.enrollAgent": "Einen Scan-Agenten registrieren",
  "dashboard.step.createScan": "Ein Scan-Profil erstellen und ausführen",
  "dashboard.step.reviewChanges": "Bestätigte Änderungen prüfen",
  "dashboard.enrolledNoneOnline": "registriert, aber keiner online",
  "dashboard.lastScan": "Letzter Scan: {when}",

  // Dashboard charts
  "trends.title": "Trends",
  "trends.changes30d": "Bestätigte Änderungen (letzte 30 Tage)",
  "trends.changes30dHint": "Tägliche Anzahl bestätigter Port- und Dienständerungen.",
  "trends.assetsByCriticality": "Assets nach Kritikalität",
  "trends.complianceStatus": "Compliance-Status",
  "trends.runsByStatus": "Scans nach Status",
  "trends.changesByType": "Änderungen nach Typ",
};
