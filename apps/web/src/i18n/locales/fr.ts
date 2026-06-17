import type { TKey } from "./en";

export const fr: Partial<Record<TKey, string>> = {
  // Navigation
  "nav.dashboard": "Tableau de bord",
  "nav.inventory": "Inventaire",
  "nav.assets": "Actifs",
  "nav.vlans": "VLAN",
  "nav.scanning": "Analyse",
  "nav.scans": "Analyses",
  "nav.agents": "Agents",
  "nav.changes": "Changements",
  "nav.tasks": "Tâches",
  "nav.compliance": "Conformité",
  "nav.assistant": "Assistant",
  "nav.admin": "Administration",
  "nav.users": "Utilisateurs",
  "nav.settings": "Paramètres",

  // Header / chrome
  "chrome.signOut": "Se déconnecter",
  "chrome.switchToLight": "Passer au mode clair",
  "chrome.switchToDark": "Passer au mode sombre",
  "chrome.language": "Langue",

  // Common actions / labels
  "common.add": "Ajouter",
  "common.save": "Enregistrer",
  "common.saving": "Enregistrement…",
  "common.cancel": "Annuler",
  "common.delete": "Supprimer",
  "common.create": "Créer",
  "common.run": "Exécuter",
  "common.test": "Tester",
  "common.close": "Fermer",
  "common.edit": "Modifier",
  "common.loading": "Chargement…",
  "common.noData": "Aucune donnée",
  "common.error": "Une erreur est survenue",

  // Dashboard
  "dashboard.apiStatus": "État de l'API :",
  "dashboard.checking": "vérification…",
  "dashboard.healthy": "opérationnelle",
  "dashboard.unreachable": "injoignable",
  "dashboard.metric.assets": "Actifs",
  "dashboard.metric.vlans": "VLAN",
  "dashboard.metric.agentsOnline": "Agents en ligne",
  "dashboard.metric.openChanges": "Changements ouverts",
  "dashboard.metric.openTasks": "Tâches ouvertes",
  "dashboard.metric.pendingRuns": "Analyses en attente",
  "dashboard.scanWaiting": "{count} analyse(s) en attente, mais aucun agent en ligne.",
  "dashboard.checkAgents": "Vérifier vos agents",
  "dashboard.gettingStarted": "Premiers pas",
  "dashboard.gettingStartedHint":
    "Suivez ces étapes pour passer d'une installation vide à la détection confirmée des changements.",
  "dashboard.step.addVlan": "Ajouter un VLAN",
  "dashboard.step.addAssets": "Ajouter des actifs à analyser",
  "dashboard.step.enrollAgent": "Enregistrer un agent d'analyse",
  "dashboard.step.createScan": "Créer un profil d'analyse et l'exécuter",
  "dashboard.step.reviewChanges": "Examiner les changements confirmés",
  "dashboard.enrolledNoneOnline": "enregistré, mais aucun en ligne",
  "dashboard.lastScan": "Dernière analyse : {when}",

  // Dashboard charts
  "trends.title": "Tendances",
  "trends.changes30d": "Changements confirmés (30 derniers jours)",
  "trends.changes30dHint": "Nombre quotidien de changements de port et de service confirmés.",
  "trends.assetsByCriticality": "Actifs par criticité",
  "trends.complianceStatus": "État de conformité",
  "trends.runsByStatus": "Analyses par statut",
  "trends.changesByType": "Changements par type",
};
