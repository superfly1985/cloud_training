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
                <th>mAP@50</th>
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
                <td class="numeric">{{ task.status !== 'running' || task.current_epoch > 0 ? task.map50.toFixed(4) : '-' }}</td>
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
                    <button v-if="task.status === 'completed'" class="btn btn-sm btn-ghost" @click="goToPackage(task)" aria-label="查看产物">
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
  },
  methods: {
    formatDate: function (iso) {
      return API.formatDate(iso);
    },
    statusBadgeClass: function (status) {
      var map = { running: "badge-info", completed: "badge-success", stopped: "badge-warning", failed: "badge-danger" };
      return map[status] || "badge-secondary";
    },
    statusText: function (status) {
      var map = { running: "运行中", completed: "已完成", stopped: "已停止", failed: "失败" };
      return map[status] || status;
    },
    load: function () {
      var self = this;
      self.loading = true;
      API.getTrainingTasks().then(function (res) {
        self.tasks = res.data.tasks;
        self.loading = false;
      });
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
      var self = this;
      API.getPackages().then(function (res) {
        var pkg = res.data.packages.find(function (p) {
          return p.dataset_name === task.dataset_name && p.version === task.version;
        });
        if (pkg) {
          self.$root.highlightPackageId = pkg.id;
          self.$root.navigateTo("package");
        } else {
          alert("未找到对应产物包");
        }
      });
    },
  },
  mounted: function () {
    this.load();
  },
});
