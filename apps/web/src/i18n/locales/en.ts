// English is the canonical locale: its keys define every translatable string.
// Other locales are Partial and fall back to English (then to the key itself).
export const en = {
  // Navigation
  "nav.dashboard": "Dashboard",
  "nav.inventory": "Inventory",
  "nav.assets": "Assets",
  "nav.vlans": "VLANs",
  "nav.scanning": "Scanning",
  "nav.scans": "Scans",
  "nav.agents": "Agents",
  "nav.changes": "Changes",
  "nav.tasks": "Tasks",
  "nav.compliance": "Compliance",
  "nav.assistant": "Assistant",
  "nav.admin": "Admin",
  "nav.users": "Users",
  "nav.settings": "Settings",

  // Header / chrome
  "chrome.signOut": "Sign out",
  "chrome.switchToLight": "Switch to light mode",
  "chrome.switchToDark": "Switch to dark mode",
  "chrome.language": "Language",

  // Common actions / labels
  "common.add": "Add",
  "common.save": "Save",
  "common.saving": "Saving…",
  "common.cancel": "Cancel",
  "common.delete": "Delete",
  "common.create": "Create",
  "common.run": "Run",
  "common.test": "Test",
  "common.close": "Close",
  "common.edit": "Edit",
  "common.loading": "Loading…",
  "common.noData": "No data yet",
  "common.error": "Something went wrong",

  // Dashboard
  "dashboard.apiStatus": "API status:",
  "dashboard.checking": "checking…",
  "dashboard.healthy": "healthy",
  "dashboard.unreachable": "unreachable",
  "dashboard.metric.assets": "Assets",
  "dashboard.metric.vlans": "VLANs",
  "dashboard.metric.agentsOnline": "Agents online",
  "dashboard.metric.openChanges": "Open changes",
  "dashboard.metric.openTasks": "Open tasks",
  "dashboard.metric.pendingRuns": "Pending runs",
  "dashboard.scanWaiting": "{count} pending scan run(s) with no agent online.",
  "dashboard.checkAgents": "Check your agents",
  "dashboard.gettingStarted": "Getting started",
  "dashboard.gettingStartedHint":
    "Follow these steps to go from an empty install to confirmed change detection.",
  "dashboard.step.addVlan": "Add a VLAN",
  "dashboard.step.addAssets": "Add assets to scan",
  "dashboard.step.enrollAgent": "Enroll a scan agent",
  "dashboard.step.createScan": "Create a scan profile and run it",
  "dashboard.step.reviewChanges": "Review confirmed changes",
  "dashboard.enrolledNoneOnline": "enrolled, but none online",
  "dashboard.lastScan": "Last scan: {when}",

  // Dashboard charts
  "trends.title": "Trends",
  "trends.changes30d": "Confirmed changes (last 30 days)",
  "trends.changes30dHint": "Daily count of confirmed port and service changes.",
  "trends.assetsByCriticality": "Assets by criticality",
  "trends.complianceStatus": "Compliance status",
  "trends.runsByStatus": "Scan runs by status",
  "trends.changesByType": "Changes by type",
};

export type TKey = keyof typeof en;
