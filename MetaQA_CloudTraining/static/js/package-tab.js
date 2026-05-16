app.component("package-tab", {
  template: `
    <div class="fade-in-up">
      <div class="page-header">
        <h1>产物包管理</h1>
        <p>下载、删除训练产物</p>
      </div>

      <div class="toolbar">
        <div class="toolbar-left">
          <div class="search-box">
            <i class="bi bi-search" aria-hidden="true"></i>
            <input type="text" class="search-input" v-model="searchQuery" placeholder="搜索产物名称…" aria-label="搜索产物包">
          </div>
        </div>
      </div>

      <div class="card">
        <div v-if="loading" style="padding: 40px; text-align: center; color: var(--color-text-muted);" aria-live="polite">
          加载中…
        </div>
        <div v-else-if="filteredPackages.length === 0 && !loading" class="empty-state">
          <div class="empty-icon"><i class="bi bi-box-seam" aria-hidden="true"></i></div>
          <div class="empty-title">{{ searchQuery ? '未找到匹配项' : '暂无产物包' }}</div>
          <div class="empty-desc" v-if="!searchQuery">完成训练后自动生成</div>
        </div>
        <template v-else>
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>数据集</th>
                <th>版本</th>
                <th>转换状态</th>
                <th>损失值</th>
                <th>大小</th>
                <th>训练时长</th>
                <th>创建时间</th>
                <th style="width: 100px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pkg in pagedPackages" :key="pkg.id" :ref="'pkg-' + pkg.id" :class="{ 'highlight-row': highlightId === pkg.id }">
                <td class="text-truncate" style="max-width: 180px;">{{ pkg.name }}</td>
                <td class="text-truncate" style="max-width: 120px;">{{ pkg.dataset_name }}</td>
                <td><span class="badge badge-secondary">{{ pkg.version }}</span></td>
                <td><span class="badge" :class="conversionBadgeClass(pkg.conversion_status)">{{ conversionStatusText(pkg.conversion_status) }}</span></td>
                <td class="numeric">
                  <div class="loss-stack">
                    <div>box: {{ formatLoss(pkg.box_loss) }}</div>
                    <div>cls: {{ formatLoss(pkg.cls_loss) }}</div>
                    <div>dfl: {{ formatLoss(pkg.dfl_loss) }}</div>
                  </div>
                </td>
                <td class="numeric">{{ formatSize(pkg.size) }}</td>
                <td>{{ pkg.training_time }}</td>
                <td>{{ formatDate(pkg.created_at) }}</td>
                <td>
                  <div style="display: flex; gap: 4px;">
                    <button class="btn btn-sm btn-ghost" @click="downloadPkg(pkg)" aria-label="下载">
                      <i class="bi bi-download" aria-hidden="true"></i>
                    </button>
                    <button class="btn btn-sm btn-ghost" @click="showDetail(pkg)" aria-label="详情">
                      <i class="bi bi-info-circle" aria-hidden="true"></i>
                    </button>
                    <button class="btn btn-sm btn-ghost btn-danger" @click="confirmDelete(pkg)" aria-label="删除">
                      <i class="bi bi-trash" aria-hidden="true"></i>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="pagination-bar" v-if="totalPages > 1">
            <div class="pagination-left">
              <span>共 {{ filteredPackages.length }} 条</span>
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
      packages: [],
      loading: true,
      searchQuery: "",
      page: 1,
      pageSize: 12,
      jumpPage: 1,
      highlightId: null,
    };
  },
  computed: {
    filteredPackages: function () {
      var q = this.searchQuery.trim().toLowerCase();
      if (!q) return this.packages;
      return this.packages.filter(function (p) {
        return p.name.toLowerCase().indexOf(q) !== -1 || p.dataset_name.toLowerCase().indexOf(q) !== -1;
      });
    },
    totalPages: function () {
      return Math.max(1, Math.ceil(this.filteredPackages.length / this.pageSize));
    },
    pagedPackages: function () {
      var start = (this.page - 1) * this.pageSize;
      return this.filteredPackages.slice(start, start + this.pageSize);
    },
    visiblePages: function () {
      return calcVisiblePages(this.page, this.totalPages);
    },
  },
  watch: {
    searchQuery: function () {
      this.page = 1;
    },
  },
  methods: {
    formatSize: function (bytes) {
      return API.formatBytes(bytes);
    },
    formatDate: function (iso) {
      return API.formatDate(iso);
    },
    formatLoss: function (value) {
      if (value === null || value === undefined || value === "") return "-";
      var num = Number(value);
      return Number.isFinite(num) && num > 0 ? num.toFixed(3) : "-";
    },
    conversionStatusText: function (status) {
      var map = { complete: "已转换", partial: "部分转换", not_converted: "未转换" };
      return map[status] || "未转换";
    },
    conversionBadgeClass: function (status) {
      var map = { complete: "badge-success", partial: "badge-warning", not_converted: "badge-secondary" };
      return map[status] || "badge-secondary";
    },
    load: function () {
      var self = this;
      self.loading = true;
      API.getPackages().then(function (res) {
        self.packages = res.data.packages;
        self.loading = false;
        self.$nextTick(function () {
          self.applyHighlight();
        });
      });
    },
    doJump: function () {
      if (this.jumpPage >= 1 && this.jumpPage <= this.totalPages) {
        this.page = this.jumpPage;
      }
    },
    applyHighlight: function () {
      var pkgId = this.$root.highlightPackageId;
      if (!pkgId) return;
      this.highlightId = pkgId;
      this.$root.highlightPackageId = null;
      var targetPkg = this.packages.find(function (p) { return p.id === pkgId; });
      if (targetPkg) {
        var idx = this.packages.indexOf(targetPkg);
        this.page = Math.floor(idx / this.pageSize) + 1;
      }
      var self = this;
      this.$nextTick(function () {
        var refKey = "pkg-" + pkgId;
        var el = self.$refs[refKey];
        if (el && el[0]) {
          el[0].scrollIntoView({ behavior: "smooth", block: "center" });
        }
        setTimeout(function () {
          self.highlightId = null;
        }, 2000);
      });
    },
    downloadPkg: function (pkg) {
      var url = API.downloadPackageUrl(pkg.id);
      var a = document.createElement("a");
      a.href = url;
      a.download = pkg.name;
      a.click();
    },
    showDetail: function (pkg) {
      this.$root.activePackageId = pkg.id;
      this.$root.showPackageDetailModal = true;
    },
    confirmDelete: function (pkg) {
      var self = this;
      self.$root.confirm({
        title: "删除产物包",
        message: "确定删除产物包「" + pkg.name + "」？此操作不可恢复。",
        danger: true,
        confirmText: "删除",
      }).then(function (ok) {
        if (!ok) return;
        API.deletePackage(pkg.id).then(function () {
          self.load();
        });
      });
    },
  },
  mounted: function () {
    this.load();
  },
});
