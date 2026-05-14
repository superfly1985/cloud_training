app.component("system-tab", {
  template: `
    <div class="fade-in-up">
      <div class="page-header">
        <h1>系统状态</h1>
        <p>环境检查、GPU 状态、系统信息</p>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">
        <div class="card">
          <div class="card-title">GPU 状态</div>
          <div style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
              <span style="font-size: 13px; color: var(--color-text-secondary);">利用率</span>
              <span class="numeric" style="font-size: 13px; font-weight: 600;">{{ sysInfo.gpu_usage }}%</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: sysInfo.gpu_usage + '%' }"></div>
            </div>
          </div>
          <div style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
              <span style="font-size: 13px; color: var(--color-text-secondary);">显存</span>
              <span class="numeric" style="font-size: 13px; font-weight: 600;">{{ sysInfo.gpu_memory_used }} GB / {{ sysInfo.gpu_memory_total }} GB</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: gpuMemPercent + '%' }"></div>
            </div>
          </div>
          <div style="font-size: 13px; color: var(--color-text-secondary); line-height: 2;">
            <div>型号: {{ sysInfo.gpu_name }}</div>
            <div>温度: {{ sysInfo.gpu_temp }} C</div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">磁盘空间</div>
          <div style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
              <span style="font-size: 13px; color: var(--color-text-secondary);">已使用</span>
              <span class="numeric" style="font-size: 13px; font-weight: 600;">{{ sysInfo.disk_used_gb }} GB / {{ sysInfo.disk_total_gb }} GB</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" :class="{ success: sysInfo.disk_usage < 80 }" :style="{ width: sysInfo.disk_usage + '%' }"></div>
            </div>
          </div>
          <div style="font-size: 13px; color: var(--color-text-secondary); line-height: 2;">
            <div>Python: {{ sysInfo.python_version }}</div>
            <div>CUDA: {{ sysInfo.cuda_version }}</div>
            <div>Ultralytics: {{ sysInfo.ultralytics_version }}</div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title" style="display: flex; align-items: center; justify-content: space-between;">
          <span>环境检查</span>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-sm btn-ghost" @click="runChecks" :disabled="checking">
              <i class="bi bi-arrow-clockwise" aria-hidden="true"></i> 重新检查
            </button>
            <button class="btn btn-sm btn-primary" @click="autoFix" :disabled="fixing">
              <span v-if="fixing" class="spinner"></span>
              自动修复
            </button>
          </div>
        </div>

        <div v-if="checks.length === 0" style="padding: 20px; text-align: center; color: var(--color-text-muted);">
          点击"重新检查"开始环境检查
        </div>

        <div v-else>
          <div v-for="check in checks" :key="check.name" class="check-item" :class="check.status">
            <div class="check-icon" :class="check.status">
              <i v-if="check.status === 'pass'" class="bi bi-check-lg" aria-hidden="true"></i>
              <i v-else-if="check.status === 'fail'" class="bi bi-x-lg" aria-hidden="true"></i>
              <i v-else-if="check.status === 'checking'" class="bi bi-arrow-repeat" aria-hidden="true"></i>
              <i v-else class="bi bi-dash" aria-hidden="true"></i>
            </div>
            <div style="flex: 1; min-width: 0;">
              <div style="font-size: 14px; font-weight: 500;">{{ check.name }}</div>
              <div style="font-size: 12px; color: var(--color-text-secondary);">{{ check.message }}</div>
            </div>
            <button v-if="check.status === 'fail' && check.auto_fixable" class="btn btn-sm btn-ghost" @click="fixOne(check)">
              修复
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
  data: function () {
    return {
      sysInfo: {
        gpu_usage: 0,
        gpu_memory_used: 0,
        gpu_memory_total: 0,
        gpu_temp: 0,
        gpu_name: "-",
        disk_usage: 0,
        disk_used_gb: 0,
        disk_total_gb: 0,
        python_version: "-",
        cuda_version: "-",
        ultralytics_version: "-",
      },
      checks: [],
      checking: false,
      fixing: false,
    };
  },
  computed: {
    gpuMemPercent: function () {
      if (!this.sysInfo.gpu_memory_total) return 0;
      return Math.round((this.sysInfo.gpu_memory_used / this.sysInfo.gpu_memory_total) * 100);
    },
  },
  methods: {
    loadSysInfo: function () {
      var self = this;
      API.getSystemStatus().then(function (res) {
        self.sysInfo = res.data;
      });
    },
    runChecks: function () {
      var self = this;
      self.checking = true;
      self.checks = [];
      API.getSystemChecks().then(function (res) {
        self.checks = res.data.checks.map(function (c) {
          return Object.assign({}, c, { status: "checking" });
        });
        var i = 0;
        function next() {
          if (i >= self.checks.length) {
            self.checking = false;
            return;
          }
          self.checks[i].status = res.data.checks[i].status;
          i++;
          setTimeout(next, 200);
        }
        next();
      });
    },
    autoFix: function () {
      var self = this;
      self.fixing = true;
      API.fixSystem().then(function () {
        self.fixing = false;
        self.runChecks();
      });
    },
    fixOne: function (check) {
      check.status = "checking";
      var self = this;
      API.fixSystem().then(function () {
        check.status = "pass";
        check.message = "已修复";
      });
    },
  },
  mounted: function () {
    this.loadSysInfo();
    this.runChecks();
  },
});
