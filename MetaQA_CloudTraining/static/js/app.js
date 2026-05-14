function calcVisiblePages(current, total) {
  if (total <= 10) {
    var pages = [];
    for (var i = 1; i <= total; i++) pages.push(i);
    return pages;
  }
  var pages = [];
  var start = Math.max(1, current - 4);
  var end = Math.min(total, current + 5);
  if (start > 1) {
    pages.push(1);
    if (start > 2) pages.push("…");
  }
  for (var i = start; i <= end; i++) pages.push(i);
  if (end < total) {
    if (end < total - 1) pages.push("…");
    pages.push(total);
  }
  return pages;
}

var app = Vue.createApp({
  data: function () {
    return {
      sidebarCollapsed: false,
      currentTab: "dashboard",
      navItems: [
        { id: "dashboard", label: "概览", icon: "bi-speedometer2" },
        { id: "dataset", label: "数据集", icon: "bi-folder2-open" },
        { id: "training", label: "训练", icon: "bi-cpu" },
        { id: "package", label: "产物", icon: "bi-box-seam" },
        { id: "system", label: "系统", icon: "bi-gear" },
      ],
      systemStatus: {
        status: "ready",
        statusText: "系统正常",
        gpuUsage: 89,
        diskUsage: 67,
        runningTasks: 2,
      },
      envFixing: false,
      envHasFailures: false,
      showCreateDatasetModal: false,
      showMergeDatasetModal: false,
      showNewTrainingModal: false,
      showTrainingLogModal: false,
      showTrainingChartModal: false,
      showPackageDetailModal: false,
      showConfirmModal: false,
      activeTaskId: null,
      activePackageId: null,
      highlightPackageId: null,
      appVersion: "0.1.0",
      confirmConfig: {},
      confirmResolve: null,
    };
  },
  methods: {
    toggleSidebar: function () {
      this.sidebarCollapsed = !this.sidebarCollapsed;
    },
    navigateTo: function (tabId) {
      var self = this;
      if (self.currentTab === tabId) return;
      if (document.startViewTransition) {
        document.startViewTransition(function () {
          self.currentTab = tabId;
          window.location.hash = "#/" + tabId;
        });
      } else {
        self.currentTab = tabId;
        window.location.hash = "#/" + tabId;
      }
    },
    handleHashChange: function () {
      var hash = window.location.hash.replace("#/", "") || "dashboard";
      var validTabs = this.navItems.map(function (n) {
        return n.id;
      });
      if (validTabs.indexOf(hash) !== -1) {
        this.currentTab = hash;
      }
    },
    loadSystemStatus: function () {
      var self = this;
      API.getSystemStatus().then(function (res) {
        var d = res.data;
        self.systemStatus = {
          status: d.status,
          statusText: d.statusText,
          gpuUsage: d.gpu_usage,
          diskUsage: d.disk_usage,
          runningTasks: d.running_tasks,
        };
      });
      if (!self.envFixing) {
        API.getSystemChecks().then(function (res) {
          if (res && res.data && res.data.checks) {
            var hasFail = res.data.checks.some(function (c) { return c.status === "fail"; });
            self.envHasFailures = hasFail;
          }
        });
      }
    },
    confirm: function (config) {
      var self = this;
      return new Promise(function (resolve) {
        self.confirmConfig = config;
        self.confirmResolve = resolve;
        self.showConfirmModal = true;
      });
    },
    handleConfirm: function () {
      this.showConfirmModal = false;
      if (this.confirmResolve) {
        this.confirmResolve(true);
        this.confirmResolve = null;
      }
    },
  },
  mounted: function () {
    this.handleHashChange();
    window.addEventListener("hashchange", this.handleHashChange);
    this.loadSystemStatus();
    var self = this;
    setInterval(function () {
      self.loadSystemStatus();
    }, 30000);
  },
  beforeUnmount: function () {
    window.removeEventListener("hashchange", this.handleHashChange);
  },
});

window.addEventListener("DOMContentLoaded", function () {
  app.mount("#app");
});
