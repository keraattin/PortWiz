import type { TKey } from "./en";

export const pt: Partial<Record<TKey, string>> = {
  // Navigation
  "nav.dashboard": "Painel",
  "nav.inventory": "Inventário",
  "nav.assets": "Ativos",
  "nav.vlans": "VLANs",
  "nav.scanning": "Varredura",
  "nav.scans": "Varreduras",
  "nav.agents": "Agentes",
  "nav.changes": "Alterações",
  "nav.tasks": "Tarefas",
  "nav.compliance": "Conformidade",
  "nav.assistant": "Assistente",
  "nav.admin": "Administração",
  "nav.users": "Usuários",
  "nav.settings": "Configurações",

  // Header / chrome
  "chrome.signOut": "Sair",
  "chrome.switchToLight": "Mudar para o modo claro",
  "chrome.switchToDark": "Mudar para o modo escuro",
  "chrome.language": "Idioma",

  // Common actions / labels
  "common.add": "Adicionar",
  "common.save": "Salvar",
  "common.saving": "Salvando…",
  "common.cancel": "Cancelar",
  "common.delete": "Excluir",
  "common.create": "Criar",
  "common.run": "Executar",
  "common.test": "Testar",
  "common.close": "Fechar",
  "common.edit": "Editar",
  "common.loading": "Carregando…",
  "common.noData": "Ainda sem dados",
  "common.error": "Algo deu errado",

  // Dashboard
  "dashboard.apiStatus": "Status da API:",
  "dashboard.checking": "verificando…",
  "dashboard.healthy": "saudável",
  "dashboard.unreachable": "inacessível",
  "dashboard.metric.assets": "Ativos",
  "dashboard.metric.vlans": "VLANs",
  "dashboard.metric.agentsOnline": "Agentes online",
  "dashboard.metric.openChanges": "Alterações abertas",
  "dashboard.metric.openTasks": "Tarefas abertas",
  "dashboard.metric.pendingRuns": "Varreduras pendentes",
  "dashboard.scanWaiting": "{count} varredura(s) pendente(s), mas nenhum agente online.",
  "dashboard.checkAgents": "Verifique seus agentes",
  "dashboard.gettingStarted": "Primeiros passos",
  "dashboard.gettingStartedHint":
    "Siga estes passos para ir de uma instalação vazia à detecção confirmada de alterações.",
  "dashboard.step.addVlan": "Adicionar uma VLAN",
  "dashboard.step.addAssets": "Adicionar ativos para varrer",
  "dashboard.step.enrollAgent": "Registrar um agente de varredura",
  "dashboard.step.createScan": "Criar um perfil de varredura e executá-lo",
  "dashboard.step.reviewChanges": "Revisar alterações confirmadas",
  "dashboard.enrolledNoneOnline": "registrado, mas nenhum online",
  "dashboard.lastScan": "Última varredura: {when}",

  // Dashboard charts
  "trends.title": "Tendências",
  "trends.changes30d": "Alterações confirmadas (últimos 30 dias)",
  "trends.changes30dHint": "Contagem diária de alterações confirmadas de portas e serviços.",
  "trends.assetsByCriticality": "Ativos por criticidade",
  "trends.complianceStatus": "Status de conformidade",
  "trends.runsByStatus": "Varreduras por status",
  "trends.changesByType": "Alterações por tipo",
};
