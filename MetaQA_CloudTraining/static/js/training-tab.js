app.component("training-tab", {
  template: `
    <div class="fade-in-up">
      <div class="page-header">
        <h1>训练任务</h1>
        <p>启动、监控、停止训练</p>
      </div>

      <div class="toolbar">
        <div class="toolbar-left">
          <div class="search-box">
            <i class="bi bi-search" aria-hidden="true"></i>
            <input type="text" class="search-input" v-model="searchQuery" placeholder="搜索数据集或版本…" aria-label="搜索训练任务">
          </div>
          <select class="filter-select" v-model="statusFilter" aria-label="状态筛选">
            <option value="">全部状态</option>
            <option value="running">运行中</option>
            <option value="converting">转换中</option>
            <option value="packaging">打包中</option>
            <option value="completed">已完成</option>
            <option value="stopped">已停止</option>
            <option value="failed">失败</option>
          </select>
        </div>
        <div class="toolbar-right">
          <button class="btn btn-primary" @click="$root.showNewTrainingModal = true">
            <i class="bi bi-plus-circle" aria-hidden="true"></i> 新建训练
          </button>
        </div>
      </div>

      <div class="card">
        <div v-if="loading" style="padding: 40px; text-align: center; color: var(--color-text-muted);" aria-live="polite">
          加载中…
        </div>
        <div v-else-if="filteredTasks.length === 0 && !loading" class="empty-state">
          <div class="empty-icon"><i class="bi bi-cpu" aria-hidden="true"></i></div>
          <div class="empty-title">{{ searchQuery || statusFilter ? '未找到匹配项' : '暂无训练任务' }}</div>
          <div class="empty-desc" v-if="!searchQuery && !statusFilter">点击"新建训练"开始</div>
        </div>
        <template v-else>
          <table>
            <thead>
              <tr>
                <th>数据集</th>
                <th>版本</th>
                <th>模型</th>
                <th>进度</th>
                <th>损失值</th>
                <th>状态</th>
                <th>创建时间</th>
                <th style="width: 160px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in pagedTasks" :key="task.id">
                <td class="text-truncate" style="max-width: 120px;">{{ task.dataset_name }}</td>
                <td><span class="badge badge-secondary">{{ task.version }}</span></td>
                <td>YOLOv8{{ task.model_size }}</td>
                <td>
                  <div v-if="task.status === 'running'" style="display: flex; align-items: center; gap: 8px;">
                    <div class="progress-bar" style="width: 60px; height: 6px;">
                      <div class="progress-fill" :style="{ width: (task.current_epoch / task.epochs * 100) + '%' }"></div>
                    </div>
                    <span style="font-size: 12px;">{{ task.current_epoch }}/{{ task.epochs }}</span>
                  </div>
                  <span v-else style="font-size: 12px; color: var(--color-text-muted);">-</span>
                </td>
                <td class="numeric">
                  <div class="loss-stack">
                    <div>box: {{ formatLoss(task.box_loss) }}</div>
                    <div>cls: {{ formatLoss(task.cls_loss) }}</div>
                    <div>dfl: {{ formatLoss(task.dfl_loss) }}</div>
                  </div>
                </td>
                <td>
                  <span class="badge" :class="statusBadgeClass(task.status)">{{ statusText(task.status) }}</span>
                </td>
                <td>{{ formatDate(task.created_at) }}</td>
                <td>
                  <div style="display: flex; gap: 4px;">
                    <button v-if="task.status === 'running'" class="btn btn-sm btn-ghost btn-danger" @click="stopTask(task)" aria-label="停止">
                      <i class="bi bi-stop-circle" aria-hidden="true"></i>
                    </button>
                    <button class="btn btn-sm btn-ghost" @click="showLog(task)" aria-label="日志">
                      <i class="bi bi-file-text" aria-hidden="true"></i>
                    </button>
                    <button class="btn btn-sm btn-ghost" @click="showChart(task)" aria-label="曲线">
                      <i class="bi bi-graph-up" aria-hidden="true"></i>
                    </button>
                    <button v-if="task.package_ready && task.package_id" class="btn btn-sm btn-ghost" @click="goToPackage(task)" aria-label="查看产物">
                      <i class="bi bi-box-seam" aria-hidden="true"></i>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="pagination-bar" v-if="totalPages > 1">
            <div class="pagination-left">
              <span>共 {{ filteredTasks.length }} 条</span>
              <button class="btn btn-sm btn-ghost" :disabled="page <= 1" @click="page = 1">首页</button>
              <button class="btn btn-sm btn-ghost" :disabled="page <= 1" @click="page--">上一页</button>
              <template v-for="p in visiblePages" :key="p">
                <span v-if="p === '…'" class="pagination-ellipsis">…</span>
                <button v-else class="btn btn-sm page-btn" :class="{ active: p === page }" @click="page = p">{{ p }}</button>
              </template>
              <button class="btn btn-sm btn-ghost" :disabled="page >= totalPages" @click="page++">下一页</button>
              <button class="btn btn-sm btn-ghost" :disabled="page >= totalPages" @click="page = totalPages">末页</button>
            </div>
            <div class="pagination-right">
              <div class="page-jump">
                跳转至第 <input type="number" class="page-jump-input" v-model.number="jumpPage" :min="1" :max="totalPages" @keyup.enter="doJump" aria-label="跳转页码"> 页
                <button class="btn btn-sm btn-ghost" @click="doJump">跳转</button>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  `,
  data: function () {
    return {
      tasks: [],
      loading: true,
      searchQuery: "",
      statusFilter: "",
      page: 1,
      pageSize: 15,
      jumpPage: 1,
      _pollTimer: null,
      _loadingPromise: null,
    };
  },
  computed: {
    filteredTasks: function () {
      var self = this;
      var result = self.tasks;
      var q = self.searchQuery.trim().toLowerCase();
      if (q) {
        result = result.filter(function (t) {
          return t.dataset_name.toLowerCase().indexOf(q) !== -1 || t.version.toLowerCase().indexOf(q) !== -1;
        });
      }
      if (self.statusFilter) {
        result = result.filter(function (t) {
          return t.status === self.statusFilter;
        });
      }
      return result;
    },
    totalPages: function () {
      return Math.max(1, Math.ceil(this.filteredTasks.length / this.pageSize));
    },
    pagedTasks: function () {
      var start = (this.page - 1) * this.pageSize;
      return this.filteredTasks.slice(start, start + this.pageSize);
    },
    visiblePages: function () {
      return calcVisiblePages(this.page, this.totalPages);
    },
  },
  watch: {
    searchQuery: function () {
      this.page = 1;
    },
    statusFilter: function () {
      this.page = 1;
    },
    "$root.showNewTrainingModal": function (newVal) {
      if (!newVal) this.load();
    },
  },
  methods: {
    formatDate: function (iso) {
      return API.formatDate(iso);
    },
    formatLoss: function (value) {
      if (value === null || value === undefined || value === "") return "-";
      var num = Number(value);
      return Number.isFinite(num) && num > 0 ? num.toFixed(3) : "-";
    },
    statusBadgeClass: function (status) {
      var map = { pending: "badge-warning", running: "badge-info", converting: "badge-info", packaging: "badge-info", completed: "badge-success", stopped: "badge-warning", failed: "badge-danger" };
      return map[status] || "badge-secondary";
    },
    statusText: function (status) {
      var map = { pending: "待启动", running: "训练中", converting: "转换中", packaging: "打包中", completed: "已完成", stopped: "已停止", failed: "失败" };
      return map[status] || status;
    },
    load: function (silent) {
      var self = this;
      if (self._loadingPromise) return self._loadingPromise;
      if (!silent) self.loading = true;
      self._loadingPromise = API.getTrainingTasks()
        .then(function (res) {
          self.tasks = (res.data && res.data.tasks) || [];
          return self.refreshActiveTasks();
        })
        .finally(function () {
          self.loading = false;
          self._loadingPromise = null;
        });
      return self._loadingPromise;
    },
    refreshActiveTasks: function () {
      var self = this;
      var activeTasks = self.tasks.filter(function (task) {
        return ["pending", "running", "converting", "packaging"].indexOf(task.status) !== -1;
      });
      if (activeTasks.length === 0) return Promise.resolve();
      return Promise.all(activeTasks.map(function (task) {
        return API.refreshMetrics(task.id).then(function (res) {
          if (res && res.code === 0 && res.data) {
            Object.assign(task, res.data);
          }
        }).catch(function () {
          return null;
        });
      }));
    },
    startPolling: function () {
      var self = this;
      self.stopPolling();
      self._pollTimer = setInterval(function () {
        self.load(true);
      }, 3000);
    },
    stopPolling: function () {
      if (this._pollTimer) {
        clearInterval(this._pollTimer);
        this._pollTimer = null;
      }
    },
    doJump: function () {
      if (this.jumpPage >= 1 && this.jumpPage <= this.totalPages) {
        this.page = this.jumpPage;
      }
    },
    stopTask: function (task) {
      var self = this;
      self.$root.confirm({
        title: "停止训练",
        message: "确定停止训练任务「" + task.dataset_name + " " + task.version + "」？",
        danger: true,
        confirmText: "停止",
      }).then(function (ok) {
        if (!ok) return;
        API.stopTraining(task.id).then(function () {
          self.load();
        });
      });
    },
    showLog: function (task) {
      this.$root.activeTaskId = task.id;
      this.$root.showTrainingLogModal = true;
    },
    showChart: function (task) {
      this.$root.activeTaskId = task.id;
      this.$root.showTrainingChartModal = true;
    },
    goToPackage: function (task) {
      if (!task.package_ready || !task.package_id) {
        alert("产物包正在生成，请稍后刷新再试");
        return;
      }
      this.$root.highlightPackageId = task.package_id;
      this.$root.navigateTo("package");
    },
  },
  mounted: function () {
    this.load();
    this.startPolling();
  },
  beforeUnmount: function () {
    this.stopPolling();
  },
});
