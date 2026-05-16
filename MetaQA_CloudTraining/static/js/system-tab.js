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
            <button class="btn btn-sm btn-ghost" @click="runChecks" :disabled="checking || fixing">
              <i class="bi bi-arrow-clockwise" aria-hidden="true"></i> 重新检查
            </button>
            <button class="btn btn-sm btn-primary" @click="autoFix" :disabled="fixing">
              <span v-if="fixing" class="spin-icon" style="margin-right: 4px;"><i class="bi bi-arrow-repeat"></i></span>
              {{ fixing ? '修复中' : '自动修复' }}
            </button>
          </div>
        </div>

        <div v-if="repairTask" class="card" style="margin-bottom: 16px; background: var(--color-bg); border-style: dashed;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px;">
            <div style="min-width: 0;">
              <div style="font-size: 14px; font-weight: 600;">
                环境修复任务
                <span class="badge"
                  :class="{
                    'badge-info': repairTask.status === 'queued' || repairTask.status === 'repairing',
                    'badge-success': repairTask.status === 'success',
                    'badge-danger': repairTask.status === 'failed'
                  }"
                  style="margin-left: 8px;"
                >
                  {{ repairStatusText }}
                </span>
              </div>
              <div style="font-size: 12px; color: var(--color-text-secondary); margin-top: 4px;">
                {{ repairTask.current_step || '等待执行' }} · 已耗时 {{ repairTask.elapsed_seconds || 0 }} 秒
              </div>
            </div>
            <div style="display: flex; gap: 8px;">
              <a
                v-if="repairTask.task_id"
                class="btn btn-sm btn-ghost"
                :href="downloadFixLogUrl"
                target="_blank"
                rel="noopener"
              >
                <i class="bi bi-download" aria-hidden="true"></i> 下载日志
              </a>
            </div>
          </div>

          <div class="progress-bar" style="height: 10px; margin-bottom: 12px;">
            <div class="progress-fill" :style="{ width: (repairTask.percent || 0) + '%' }"></div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
            <div>
              <div
                v-for="step in repairTask.steps"
                :key="step.name"
                class="check-item"
                :class="step.status === 'success' ? 'pass' : (step.status === 'failed' ? 'fail' : (step.status === 'running' ? 'checking' : ''))"
                style="padding: 10px 12px;"
              >
                <div class="check-icon" :class="step.status === 'success' ? 'pass' : (step.status === 'failed' ? 'fail' : (step.status === 'running' ? 'checking' : 'pending'))">
                  <i v-if="step.status === 'success'" class="bi bi-check-lg" aria-hidden="true"></i>
                  <i v-else-if="step.status === 'failed'" class="bi bi-x-lg" aria-hidden="true"></i>
                  <span v-else-if="step.status === 'running'" class="spin-icon" aria-hidden="true"><i class="bi bi-arrow-repeat"></i></span>
                  <i v-else class="bi bi-dash" aria-hidden="true"></i>
                </div>
                <div style="font-size: 13px; font-weight: 500;">{{ step.name }}</div>
              </div>
            </div>

            <div class="log-container" style="max-height: 280px;">
              <div v-if="!repairTask.logs || repairTask.logs.length === 0" class="log-line">暂无日志</div>
              <div v-for="(line, idx) in repairTask.logs" :key="idx" class="log-line">{{ line }}</div>
            </div>
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
              <span v-else-if="check.status === 'checking'" class="spin-icon" aria-hidden="true"><i class="bi bi-arrow-repeat"></i></span>
              <i v-else class="bi bi-dash" aria-hidden="true"></i>
            </div>
            <div style="flex: 1; min-width: 0;">
              <div style="font-size: 14px; font-weight: 500;">{{ check.name }}</div>
              <div style="font-size: 12px; color: var(--color-text-secondary);">{{ check.message }}</div>
            </div>
            <button v-if="check.status === 'fail' && check.auto_fixable" class="btn btn-sm btn-ghost" @click="fixOne(check)">
              统一修复
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
      checkTask: null,
      repairTask: null,
      _checkTimer: null,
      _fixTimer: null,
    };
  },
  computed: {
    gpuMemPercent: function () {
      if (!this.sysInfo.gpu_memory_total) return 0;
      return Math.round((this.sysInfo.gpu_memory_used / this.sysInfo.gpu_memory_total) * 100);
    },
    repairStatusText: function () {
      if (!this.repairTask) return "";
      var map = {
        queued: "排队中",
        repairing: "修复中",
        success: "已完成",
        failed: "失败",
      };
      return map[this.repairTask.status] || this.repairTask.status;
    },
    downloadFixLogUrl: function () {
      if (!this.repairTask || !this.repairTask.task_id) return "#";
      return API.downloadSystemFixLogUrl(this.repairTask.task_id);
    },
  },
  methods: {
    loadSysInfo: function () {
      var self = this;
      API.getSystemStatus().then(function (res) {
        self.sysInfo = res.data;
        if (self.$root) {
          self.$root.envHasFailures = res.data.status === "failed" || res.data.status === "partial";
        }
      });
    },
    loadChecks: function () {
      var self = this;
      API.getSystemChecks().then(function (res) {
        self.updateCheckTask(res.data);
        if (self.checking && self.checkTask && self.checkTask.task_id) {
          self.pollCheckTask(self.checkTask.task_id);
        }
      }).catch(function () {
        self.checking = false;
      });
    },
    runChecks: function () {
      var self = this;
      self.checking = true;
      self.stopCheckPolling();
      API.startSystemChecks().then(function (res) {
        self.updateCheckTask(res.data);
        if (res.data && res.data.task_id) {
          self.pollCheckTask(res.data.task_id);
        }
      }).catch(function () {
        self.checking = false;
      });
    },
    autoFix: function () {
      var self = this;
      self.fixing = true;
      if (self.$root) self.$root.envFixing = true;
      API.fixSystem().then(function (res) {
        self.repairTask = res.data;
        self.pollFixTask(res.data.task_id);
      }).catch(function () {
        self.fixing = false;
        if (self.$root) self.$root.envFixing = false;
      });
    },
    fixOne: function (check) {
      if (check) {
        check.status = "checking";
      }
      this.autoFix();
    },
    pollFixTask: function (taskId) {
      var self = this;
      if (!taskId) return;
      if (self._fixTimer) {
        clearTimeout(self._fixTimer);
        self._fixTimer = null;
      }
      API.getSystemFixStatus(taskId).then(function (res) {
        self.repairTask = res.data;
        self.fixing = res.data.status === "queued" || res.data.status === "repairing";
        if (self.$root) self.$root.envFixing = self.fixing;
        if (self.fixing) {
          self._fixTimer = setTimeout(function () {
            self.pollFixTask(taskId);
          }, 1500);
          return;
        }
        if (self.$root) self.$root.envFixing = false;
        self.loadChecks();
        self.loadSysInfo();
      }).catch(function () {
        self.fixing = false;
        if (self.$root) self.$root.envFixing = false;
      });
    },
    resumeFixingIfNeeded: function () {
      var self = this;
      API.getSystemFixCurrent().then(function (res) {
        if (!res.data || !res.data.task_id) return;
        self.repairTask = res.data;
        if (res.data.status === "queued" || res.data.status === "repairing") {
          self.fixing = true;
          if (self.$root) self.$root.envFixing = true;
          self.pollFixTask(res.data.task_id);
        }
      }).catch(function () {});
    },
    updateCheckTask: function (task) {
      this.checkTask = task || null;
      this.checks = (task && task.checks) || [];
      this.checking = !!(task && (task.status === "queued" || task.status === "checking"));
      if (this.$root) {
        var summary = task && task.summary;
        this.$root.envHasFailures = !!(summary && (summary.status === "failed" || summary.status === "partial"));
      }
    },
    pollCheckTask: function (taskId) {
      var self = this;
      if (!taskId) return;
      self.stopCheckPolling();
      API.getSystemChecks().then(function (res) {
        self.updateCheckTask(res.data);
        if (self.checking && self.checkTask && self.checkTask.task_id === taskId) {
          self._checkTimer = setTimeout(function () {
            self.pollCheckTask(taskId);
          }, 1500);
        }
      }).catch(function () {
        self.checking = false;
      });
    },
    stopCheckPolling: function () {
      if (this._checkTimer) {
        clearTimeout(this._checkTimer);
        this._checkTimer = null;
      }
    },
    stopFixPolling: function () {
      if (this._fixTimer) {
        clearTimeout(this._fixTimer);
        this._fixTimer = null;
      }
    },
  },
  mounted: function () {
    this.loadSysInfo();
    this.loadChecks();
    this.resumeFixingIfNeeded();
  },
  beforeUnmount: function () {
    this.stopCheckPolling();
    this.stopFixPolling();
  },
});
