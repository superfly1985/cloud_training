app.component("dashboard-tab", {
  template: `
    <div class="fade-in-up">
      <div class="page-header">
        <h1>概览</h1>
        <p>YOLO云算运行状态总览</p>
      </div>

      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">数据集</div>
          <div class="stat-value">{{ stats.datasetCount }}</div>
          <div class="stat-sub">{{ stats.totalImages }} 张图片</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">训练任务</div>
          <div class="stat-value">{{ stats.runningTasks }}</div>
          <div class="stat-sub">运行中 / 共 {{ stats.totalTasks }} 个</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">产物包</div>
          <div class="stat-value">{{ stats.packageCount }}</div>
          <div class="stat-sub">{{ stats.packageSize }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">GPU 利用率</div>
          <div class="stat-value">{{ stats.gpuUsage }}%</div>
          <div class="stat-sub">{{ stats.gpuName }}</div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        <div class="card">
          <div class="card-title">最近训练任务</div>
          <div v-if="recentTasks.length === 0" class="empty-state" style="padding: 30px;">
            <div class="empty-title">暂无训练任务</div>
          </div>
          <table v-else>
            <thead>
              <tr>
                <th>数据集</th>
                <th>版本</th>
                <th>状态</th>
                <th>mAP@50</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in recentTasks" :key="task.id">
                <td class="text-truncate" style="max-width: 140px;">{{ task.dataset_name }}</td>
                <td><span class="badge badge-secondary">{{ task.version }}</span></td>
                <td>
                  <span class="badge" :class="statusBadgeClass(task.status)">{{ statusText(task.status) }}</span>
                </td>
                <td class="numeric">{{ task.status !== 'running' || task.current_epoch > 0 ? task.map50.toFixed(4) : '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <div class="card-title">磁盘使用</div>
          <div style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
              <span style="font-size: 13px; color: var(--color-text-secondary);">已使用 {{ stats.diskUsedGb }} GB / {{ stats.diskTotalGb }} GB</span>
              <span class="numeric" style="font-size: 13px; font-weight: 600;">{{ stats.diskUsage }}%</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" :class="{ success: stats.diskUsage < 80 }" :style="{ width: stats.diskUsage + '%' }"></div>
            </div>
          </div>

          <div class="card-title" style="margin-top: 24px;">GPU 显存</div>
          <div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
              <span style="font-size: 13px; color: var(--color-text-secondary);">已使用 {{ stats.gpuMemUsed }} GB / {{ stats.gpuMemTotal }} GB</span>
              <span class="numeric" style="font-size: 13px; font-weight: 600;">{{ stats.gpuMemPercent }}%</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: stats.gpuMemPercent + '%' }"></div>
            </div>
          </div>

          <div style="margin-top: 24px;">
            <div class="card-title">环境信息</div>
            <div style="font-size: 13px; color: var(--color-text-secondary); line-height: 2;">
              <div>Python: {{ stats.pythonVersion }}</div>
              <div>CUDA: {{ stats.cudaVersion }}</div>
              <div>Ultralytics: {{ stats.ultralyticsVersion }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  data: function () {
    return {
      stats: {
        datasetCount: 0,
        totalImages: 0,
        runningTasks: 0,
        totalTasks: 0,
        packageCount: 0,
        packageSize: "0 MB",
        gpuUsage: 0,
        gpuName: "-",
        diskUsage: 0,
        diskUsedGb: 0,
        diskTotalGb: 0,
        gpuMemUsed: 0,
        gpuMemTotal: 0,
        gpuMemPercent: 0,
        pythonVersion: "-",
        cudaVersion: "-",
        ultralyticsVersion: "-",
      },
      recentTasks: [],
    };
  },
  methods: {
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
      Promise.all([API.getDatasets(), API.getTrainingTasks(), API.getPackages(), API.getSystemStatus()]).then(
        function (results) {
          var ds = results[0].data;
          var ts = results[1].data;
          var pkgs = results[2].data;
          var sys = results[3].data;

          self.stats.datasetCount = ds.datasets.length;
          self.stats.totalImages = ds.datasets.reduce(function (s, d) {
            return s + d.image_count;
          }, 0);
          self.stats.runningTasks = ts.tasks.filter(function (t) {
            return t.status === "running";
          }).length;
          self.stats.totalTasks = ts.tasks.length;
          self.stats.packageCount = pkgs.packages.length;
          self.stats.packageSize = API.formatBytes(
            pkgs.packages.reduce(function (s, p) {
              return s + p.size;
            }, 0)
          );
          self.stats.gpuUsage = sys.gpu_usage;
          self.stats.gpuName = sys.gpu_name;
          self.stats.diskUsage = sys.disk_usage;
          self.stats.diskUsedGb = sys.disk_used_gb;
          self.stats.diskTotalGb = sys.disk_total_gb;
          self.stats.gpuMemUsed = sys.gpu_memory_used;
          self.stats.gpuMemTotal = sys.gpu_memory_total;
          self.stats.gpuMemPercent = Math.round((sys.gpu_memory_used / sys.gpu_memory_total) * 100);
          self.stats.pythonVersion = sys.python_version;
          self.stats.cudaVersion = sys.cuda_version;
          self.stats.ultralyticsVersion = sys.ultralytics_version;

          self.recentTasks = ts.tasks.slice(0, 5);
        }
      );
    },
  },
  mounted: function () {
    this.load();
  },
});
