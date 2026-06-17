import type { TKey } from "./en";

export const tr: Partial<Record<TKey, string>> = {
  // Navigation
  "nav.dashboard": "Panel",
  "nav.inventory": "Envanter",
  "nav.assets": "Varlıklar",
  "nav.vlans": "VLAN'lar",
  "nav.scanning": "Tarama",
  "nav.scans": "Taramalar",
  "nav.agents": "Ajanlar",
  "nav.changes": "Değişiklikler",
  "nav.tasks": "Görevler",
  "nav.compliance": "Uyumluluk",
  "nav.assistant": "Asistan",
  "nav.admin": "Yönetim",
  "nav.users": "Kullanıcılar",
  "nav.settings": "Ayarlar",

  // Header / chrome
  "chrome.signOut": "Çıkış yap",
  "chrome.switchToLight": "Açık temaya geç",
  "chrome.switchToDark": "Koyu temaya geç",
  "chrome.language": "Dil",

  // Common actions / labels
  "common.add": "Ekle",
  "common.save": "Kaydet",
  "common.saving": "Kaydediliyor…",
  "common.cancel": "İptal",
  "common.delete": "Sil",
  "common.create": "Oluştur",
  "common.run": "Çalıştır",
  "common.test": "Test et",
  "common.close": "Kapat",
  "common.edit": "Düzenle",
  "common.loading": "Yükleniyor…",
  "common.noData": "Henüz veri yok",
  "common.error": "Bir şeyler ters gitti",

  // Dashboard
  "dashboard.apiStatus": "API durumu:",
  "dashboard.checking": "kontrol ediliyor…",
  "dashboard.healthy": "sağlıklı",
  "dashboard.unreachable": "erişilemiyor",
  "dashboard.metric.assets": "Varlıklar",
  "dashboard.metric.vlans": "VLAN'lar",
  "dashboard.metric.agentsOnline": "Çevrimiçi ajanlar",
  "dashboard.metric.openChanges": "Açık değişiklikler",
  "dashboard.metric.openTasks": "Açık görevler",
  "dashboard.metric.pendingRuns": "Bekleyen taramalar",
  "dashboard.scanWaiting": "{count} bekleyen tarama var ama çevrimiçi ajan yok.",
  "dashboard.checkAgents": "Ajanları kontrol et",
  "dashboard.gettingStarted": "Başlarken",
  "dashboard.gettingStartedHint":
    "Boş bir kurulumdan teyitli değişiklik tespitine ulaşmak için şu adımları izleyin.",
  "dashboard.step.addVlan": "Bir VLAN ekle",
  "dashboard.step.addAssets": "Taranacak varlıklar ekle",
  "dashboard.step.enrollAgent": "Bir tarama ajanı kaydet",
  "dashboard.step.createScan": "Bir tarama profili oluştur ve çalıştır",
  "dashboard.step.reviewChanges": "Teyitli değişiklikleri incele",
  "dashboard.enrolledNoneOnline": "kayıtlı ama çevrimiçi değil",
  "dashboard.lastScan": "Son tarama: {when}",

  // Dashboard charts
  "trends.title": "Eğilimler",
  "trends.changes30d": "Teyitli değişiklikler (son 30 gün)",
  "trends.changes30dHint": "Teyitli port ve servis değişikliklerinin günlük sayısı.",
  "trends.assetsByCriticality": "Kritikliğe göre varlıklar",
  "trends.complianceStatus": "Uyumluluk durumu",
  "trends.runsByStatus": "Duruma göre taramalar",
  "trends.changesByType": "Türe göre değişiklikler",
};
