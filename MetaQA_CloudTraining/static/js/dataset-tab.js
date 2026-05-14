var BBOX_COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#DDA0DD',
  '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9', '#F8C471',
  '#82E0AA', '#F1948A', '#85929E', '#AED6F1', '#E59866',
  '#C39BD3', '#7FB3D8', '#76D7C4', '#F0B27A', '#FF3838',
];

function computeBBoxColor(classId) {
  var idx = typeof classId === 'number' ? classId : parseInt(classId, 10);
  if (isNaN(idx)) {
    var hash = 0;
    for (var i = 0; i < String(classId).length; i++) {
      hash = String(classId).charCodeAt(i) + ((hash << 5) - hash);
    }
    idx = Math.abs(hash);
  }
  return BBOX_COLORS[idx % BBOX_COLORS.length];
}

app.component("dataset-tab", {
  template: `
    <div class="fade-in-up">
      <div class="page-header">
        <h1>数据集管理</h1>
        <p>创建、合并、删除数据集</p>
      </div>

      <div class="toolbar">
        <div class="toolbar-left">
          <div class="search-box">
            <i class="bi bi-search" aria-hidden="true"></i>
            <input type="text" class="search-input" v-model="searchQuery" placeholder="搜索数据集名称…" aria-label="搜索数据集">
          </div>
        </div>
        <div class="toolbar-right">
          <button class="btn btn-primary" @click="$root.showMergeDatasetModal = true">
            <i class="bi bi-plus-circle" aria-hidden="true"></i> 合并新增
          </button>
          <button class="btn btn-primary" @click="$root.showCreateDatasetModal = true">
            <i class="bi bi-plus-circle" aria-hidden="true"></i> 创建数据集
          </button>
        </div>
      </div>

      <div class="card" style="margin-bottom: 16px;">
        <div v-if="loading" style="padding: 40px; text-align: center; color: var(--color-text-muted);" aria-live="polite">
          加载中…
        </div>
        <div v-else-if="filteredDatasets.length === 0 && !loading" class="empty-state">
          <div class="empty-icon"><i class="bi bi-folder2-open" aria-hidden="true"></i></div>
          <div class="empty-title">{{ searchQuery ? '未找到匹配项' : '暂无数据集' }}</div>
          <div class="empty-desc" v-if="!searchQuery">点击"创建数据集"开始</div>
        </div>
        <template v-else>
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>图片数</th>
                <th>已标注</th>
                <th>类别</th>
                <th>大小</th>
                <th>更新时间</th>
                <th style="width: 80px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ds in pagedDatasets" :key="ds.id">
                <td>
                  <a href="#" @click.prevent="viewDataset(ds)" class="link">{{ ds.name }}</a>
                </td>
                <td class="numeric">{{ ds.image_count }}</td>
                <td class="numeric">{{ ds.annotated_count }}</td>
                <td>
                  <span v-for="cls in ds.classes.slice(0, 3)" :key="cls.id" class="badge" :style="{ background: getBBoxColor(cls.id), color: '#fff', marginRight: '4px' }">{{ cls.name }}</span>
                  <span v-if="ds.classes.length > 3" class="badge badge-secondary">+{{ ds.classes.length - 3 }}</span>
                </td>
                <td class="numeric">{{ formatSize(ds.total_size) }}</td>
                <td>{{ formatDate(ds.updated_at) }}</td>
                <td>
                  <button class="btn btn-sm btn-ghost btn-danger" @click="confirmDelete(ds)" aria-label="删除数据集">
                    <i class="bi bi-trash" aria-hidden="true"></i>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="pagination-bar" v-if="dsTotalPages > 1">
            <div class="pagination-left">
              <span>共 {{ filteredDatasets.length }} 条</span>
              <button class="btn btn-sm btn-ghost" :disabled="dsPage <= 1" @click="dsPage = 1">首页</button>
              <button class="btn btn-sm btn-ghost" :disabled="dsPage <= 1" @click="dsPage--">上一页</button>
              <template v-for="p in dsVisiblePages" :key="p">
                <span v-if="p === '…'" class="pagination-ellipsis">…</span>
                <button v-else class="btn btn-sm page-btn" :class="{ active: p === dsPage }" @click="dsPage = p">{{ p }}</button>
              </template>
              <button class="btn btn-sm btn-ghost" :disabled="dsPage >= dsTotalPages" @click="dsPage++">下一页</button>
              <button class="btn btn-sm btn-ghost" :disabled="dsPage >= dsTotalPages" @click="dsPage = dsTotalPages">末页</button>
            </div>
            <div class="pagination-right">
              <div class="page-jump">
                跳转至第 <input type="number" class="page-jump-input" v-model.number="dsJumpPage" :min="1" :max="dsTotalPages" @keyup.enter="dsJump" aria-label="跳转页码"> 页
                <button class="btn btn-sm btn-ghost" @click="dsJump">跳转</button>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div v-if="selectedDataset" class="card">
        <div class="card-title" style="display: flex; align-items: center; justify-content: space-between;">
          <span>{{ selectedDataset.name }} - 图片浏览</span>
          <button class="btn btn-sm btn-ghost" @click="closeDataset">关闭</button>
        </div>
        <div v-if="imagesLoading" style="padding: 40px; text-align: center; color: var(--color-text-muted);" aria-live="polite">加载中…</div>
        <div v-else class="dataset-layout">
          <div class="dataset-list-panel">
            <div class="dataset-list-header">
              <label class="checkbox-label">
                <input type="checkbox" :checked="allImagesSelected" @change="toggleSelectAll" :indeterminate.prop="images.length > 0 && selectedImageIds.length > 0 && selectedImageIds.length < images.length" aria-label="全选/取消全选">
                <span>{{ selectedImageIds.length > 0 ? '已选 ' + selectedImageIds.length : '图片列表' }}</span>
              </label>
            </div>
            <div class="dataset-list-body">
              <div v-for="(img, index) in images" :key="img.id" class="dataset-item" :class="{ selected: selectedImageIds.indexOf(img.id) !== -1 }" @click="onItemClick(img.id, index, $event)">
                <input type="checkbox" class="item-checkbox" :checked="selectedImageIds.indexOf(img.id) !== -1" @click.stop="toggleImageSelect(img.id)" :aria-label="'选择 ' + img.filename">
                <img v-if="img.thumbnail_url" :src="img.thumbnail_url" :alt="img.filename" class="item-thumb" width="40" height="40" loading="lazy">
                <div v-else class="item-thumb" style="display: flex; align-items: center; justify-content: center;">
                  <i class="bi bi-image" aria-hidden="true" style="font-size: 18px; color: var(--color-text-muted);"></i>
                </div>
                <div class="item-info">
                  <div class="item-name" :title="img.filename">{{ truncateFilename(img.filename) }}</div>
                  <div class="item-size">
                    <span :class="img.annotated ? 'text-success' : 'text-muted'">{{ img.annotated ? '已标注' : '未标注' }}</span>
                    {{ formatSize(img.size) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="preview-panel">
            <div v-if="!previewImage" class="preview-placeholder">
              <i class="bi bi-image" aria-hidden="true" style="font-size: 48px; display: block; margin-bottom: 12px;"></i>
              选择图片预览
            </div>
            <div v-else class="preview-content">
              <div class="preview-image-box">
                <div class="preview-aspect-ratio" ref="previewContainer">
                  <template v-if="previewImage.thumbnail_url">
                    <img :src="previewImage.thumbnail_url" :alt="previewImage.filename"
                         @load="onPreviewImageLoad"
                         ref="previewImg"
                         style="width: 100%; height: 100%; object-fit: contain;">
                    <canvas ref="bboxCanvas" class="bbox-canvas"></canvas>
                  </template>
                  <div v-else class="preview-placeholder" style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;">
                    <i class="bi bi-image" aria-hidden="true" style="font-size: 48px;"></i>
                  </div>
                </div>
              </div>
              <div class="preview-info">
                <div class="preview-filename">{{ previewImage.filename }}</div>
                <div class="preview-meta">
                  {{ previewImage.width }} × {{ previewImage.height }} · {{ formatSize(previewImage.size) }} ·
                  <span :class="previewImage.annotated ? 'text-success' : 'text-muted'">{{ previewImage.annotated ? '已标注' : '未标注' }}</span>
                  <span v-if="imageLabels.length > 0"> · {{ imageLabels.length }} 个标注</span>
                </div>
                <div v-if="classNamesList.length > 0" class="bbox-legend">
                  <span v-for="item in classNamesList" :key="item.id" class="bbox-legend-item">
                    <span class="bbox-legend-color" :style="{ background: item.color }"></span>
                    {{ item.name }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="pagination-bar" v-if="imgTotal > 0" style="margin-top: 0; border-top: 1px solid var(--color-border); border-bottom: none;">
          <div class="pagination-left">
            <span>共 {{ imgTotal }} 张</span>
            <button class="btn btn-sm btn-ghost" :disabled="imgPage <= 1" @click="imgPage = 1">首页</button>
            <button class="btn btn-sm btn-ghost" :disabled="imgPage <= 1" @click="imgPage--">上一页</button>
            <template v-for="p in imgVisiblePages" :key="'ip-'+p">
              <span v-if="p === '…'" class="pagination-ellipsis">…</span>
              <button v-else class="btn btn-sm page-btn" :class="{ active: p === imgPage }" @click="imgPage = p">{{ p }}</button>
            </template>
            <button class="btn btn-sm btn-ghost" :disabled="imgPage >= imgTotalPages" @click="imgPage++">下一页</button>
            <button class="btn btn-sm btn-ghost" :disabled="imgPage >= imgTotalPages" @click="imgPage = imgTotalPages">末页</button>
          </div>
          <div class="pagination-right" style="display: flex; align-items: center; gap: 8px;">
            <div class="page-jump">
              跳转至第 <input type="number" class="page-jump-input" v-model.number="imgJumpPage" :min="1" :max="imgTotalPages" @keyup.enter="imgJump" aria-label="跳转图片页码"> 页
              <button class="btn btn-sm btn-ghost" @click="imgJump">跳转</button>
            </div>
            <button class="btn btn-sm btn-danger" v-if="selectedImageIds.length > 0" @click="deleteSelectedImages">
              <i class="bi bi-trash" aria-hidden="true"></i> 删除选中 ({{ selectedImageIds.length }})
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
  data: function () {
    return {
      datasets: [],
      loading: true,
      searchQuery: "",
      dsPage: 1,
      dsPageSize: 8,
      dsJumpPage: 1,
      selectedDataset: null,
      images: [],
      imagesLoading: false,
      imgPage: 1,
      imgPageSize: 20,
      imgTotal: 0,
      imgJumpPage: 1,
      selectedImageIds: [],
      previewImage: null,
      lastClickedIndex: -1,
      imageLabels: [],
      classColorMap: {},
      classNamesList: [],
    };
  },
  computed: {
    filteredDatasets: function () {
      var q = this.searchQuery.trim().toLowerCase();
      if (!q) return this.datasets;
      return this.datasets.filter(function (ds) {
        return ds.name.toLowerCase().indexOf(q) !== -1;
      });
    },
    dsTotalPages: function () {
      return Math.max(1, Math.ceil(this.filteredDatasets.length / this.dsPageSize));
    },
    pagedDatasets: function () {
      var start = (this.dsPage - 1) * this.dsPageSize;
      return this.filteredDatasets.slice(start, start + this.dsPageSize);
    },
    dsVisiblePages: function () {
      return calcVisiblePages(this.dsPage, this.dsTotalPages);
    },
    imgTotalPages: function () {
      return Math.max(1, Math.ceil(this.imgTotal / this.imgPageSize));
    },
    imgVisiblePages: function () {
      return calcVisiblePages(this.imgPage, this.imgTotalPages);
    },
    allImagesSelected: function () {
      return this.images.length > 0 && this.selectedImageIds.length === this.images.length;
    },
  },
  watch: {
    searchQuery: function () {
      this.dsPage = 1;
    },
    imgPage: function () {
      this.loadImages();
    },
    "$root.showCreateDatasetModal": function (newVal) {
      if (!newVal) this.load();
    },
    "$root.showMergeDatasetModal": function (newVal) {
      if (!newVal) this.load();
    },
  },
  methods: {
    truncateFilename: function (name) {
      if (!name) return "";
      var dotIdx = name.lastIndexOf(".");
      var ext = dotIdx > 0 ? name.substring(dotIdx) : "";
      var base = dotIdx > 0 ? name.substring(0, dotIdx) : name;
      if (base.length <= 9) return name;
      return base.substring(0, 6) + "***" + base.substring(base.length - 3) + ext;
    },
    getBBoxColor: function (classId) {
      return computeBBoxColor(classId);
    },
    formatSize: function (bytes) {
      return API.formatBytes(bytes);
    },
    formatDate: function (iso) {
      return API.formatDate(iso);
    },
    load: function () {
      var self = this;
      self.loading = true;
      API.getDatasets().then(function (res) {
        self.datasets = res.data.datasets;
        self.loading = false;
      });
    },
    viewDataset: function (ds) {
      this.selectedDataset = ds;
      this.imgPage = 1;
      this.selectedImageIds = [];
      this.previewImage = null;
      this.imageLabels = [];
      this.classColorMap = {};
      this.classNamesList = [];
      this.loadImages();
    },
    closeDataset: function () {
      this.selectedDataset = null;
      this.imageLabels = [];
      this.classColorMap = {};
      this.classNamesList = [];
    },
    loadImages: function () {
      if (!this.selectedDataset) return;
      var self = this;
      self.imagesLoading = true;
      self.previewImage = null;
      self.imageLabels = [];
      self.classNamesList = [];
      API.getDatasetImages(self.selectedDataset.id, self.imgPage, self.imgPageSize).then(function (res) {
        self.images = res.data.images;
        self.imgTotal = res.data.total;
        self.imagesLoading = false;
      });
    },
    dsJump: function () {
      if (this.dsJumpPage >= 1 && this.dsJumpPage <= this.dsTotalPages) {
        this.dsPage = this.dsJumpPage;
      }
    },
    imgJump: function () {
      if (this.imgJumpPage >= 1 && this.imgJumpPage <= this.imgTotalPages) {
        this.imgPage = this.imgJumpPage;
      }
    },
    toggleSelectAll: function () {
      var self = this;
      if (self.allImagesSelected) {
        self.selectedImageIds = [];
      } else {
        self.selectedImageIds = self.images.map(function (img) { return img.id; });
      }
    },
    toggleImageSelect: function (id) {
      var idx = this.selectedImageIds.indexOf(id);
      if (idx === -1) this.selectedImageIds.push(id);
      else this.selectedImageIds.splice(idx, 1);
    },
    onItemClick: function (id, index, event) {
      if (event.ctrlKey || event.metaKey) {
        this.toggleImageSelect(id);
        this.lastClickedIndex = index;
        return;
      }
      if (event.shiftKey && this.lastClickedIndex >= 0) {
        var self = this;
        var start = Math.min(this.lastClickedIndex, index);
        var end = Math.max(this.lastClickedIndex, index);
        for (var i = start; i <= end; i++) {
          var imgId = self.images[i].id;
          if (self.selectedImageIds.indexOf(imgId) === -1) {
            self.selectedImageIds.push(imgId);
          }
        }
        return;
      }
      this.lastClickedIndex = index;
      this.imageLabels = [];
      this.classNamesList = [];
      this.clearCanvas();
      var img = this.images.find(function (im) { return im.id === id; });
      if (img) {
        this.previewImage = img;
        this.loadImageLabels(img);
      }
    },
    onPreviewImageLoad: function () {
      this.drawBBoxes();
    },
    loadImageLabels: function (img) {
      var self = this;
      self.imageLabels = [];
      if (!img || !img.annotated) {
        self.classNamesList = [];
        self.$nextTick(function () {
          self.clearCanvas();
        });
        return;
      }
      API.getImageLabels(self.selectedDataset.id, img.filename).then(function (res) {
        var data = res.data;
        self.imageLabels = data.labels || [];
        self._buildClassColorMap(data.class_names || {});
        self.$nextTick(function () {
          self.drawBBoxes();
        });
      }).catch(function () {
        self.imageLabels = [];
        self.classNamesList = [];
        self.clearCanvas();
      });
    },
    _buildClassColorMap: function (classNames) {
      var self = this;
      var map = {};
      var list = [];
      var keys = Object.keys(classNames);
      keys.sort(function (a, b) {
        var na = parseInt(a, 10);
        var nb = parseInt(b, 10);
        if (!isNaN(na) && !isNaN(nb)) return na - nb;
        return a.localeCompare(b);
      });
      keys.forEach(function (key) {
        var color = computeBBoxColor(key);
        map[key] = color;
        list.push({ id: key, name: classNames[key], color: color });
      });
      self.classColorMap = map;
      self.classNamesList = list;
    },
    clearCanvas: function () {
      var canvas = this.$refs.bboxCanvas;
      if (!canvas) return;
      var ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      canvas.style.display = "none";
    },
    drawBBoxes: function () {
      var self = this;
      var canvas = self.$refs.bboxCanvas;
      var img = self.$refs.previewImg;
      var container = self.$refs.previewContainer;
      if (!canvas || !img || !container) return;

      var labels = self.imageLabels;
      if (!labels || labels.length === 0) {
        self.clearCanvas();
        return;
      }

      var containerRect = container.getBoundingClientRect();
      var containerW = containerRect.width;
      var containerH = containerRect.height;
      var imgW = img.naturalWidth || img.width;
      var imgH = img.naturalHeight || img.height;

      if (!imgW || !imgH || !containerW || !containerH) return;

      var scale = Math.min(containerW / imgW, containerH / imgH);
      var displayW = imgW * scale;
      var displayH = imgH * scale;
      var offsetX = (containerW - displayW) / 2;
      var offsetY = (containerH - displayH) / 2;

      var dpr = window.devicePixelRatio || 1;
      canvas.width = displayW * dpr;
      canvas.height = displayH * dpr;
      canvas.style.width = displayW + "px";
      canvas.style.height = displayH + "px";
      canvas.style.left = offsetX + "px";
      canvas.style.top = offsetY + "px";
      canvas.style.display = "block";

      var ctx = canvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, displayW, displayH);

      var lineWidth = Math.max(2, displayW / 300);

      labels.forEach(function (label) {
        var x = (label.x_center - label.width / 2) * displayW;
        var y = (label.y_center - label.height / 2) * displayH;
        var w = label.width * displayW;
        var h = label.height * displayH;

        var color = self.classColorMap[label.class_id] || computeBBoxColor(label.class_id);

        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.strokeRect(x, y, w, h);

        var text = label.class_name;
        var fontSize = Math.max(10, Math.min(16, displayW / 40));
        ctx.font = "bold " + fontSize + "px 'Segoe UI', sans-serif";
        var textMetrics = ctx.measureText(text);
        var textW = textMetrics.width;
        var textH = fontSize + 4;
        var padding = 3;

        var labelY = y - textH - 2;
        if (labelY < 0) labelY = y;

        ctx.fillStyle = color;
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.fillRect(x, labelY, textW + padding * 2, textH);
        ctx.strokeRect(x, labelY, textW + padding * 2, textH);

        ctx.fillStyle = "#ffffff";
        ctx.fillText(text, x + padding, labelY + fontSize - 1);
      });
    },
    deleteSelectedImages: function () {
      var self = this;
      if (self.selectedImageIds.length === 0) return;
      self.$root.confirm({
        title: "删除图片",
        message: "确定删除选中的 " + self.selectedImageIds.length + " 张图片？此操作不可恢复。",
        danger: true,
        confirmText: "删除",
      }).then(function (ok) {
        if (!ok) return;
        API.deleteImages(self.selectedDataset.id, self.selectedImageIds).then(function () {
          self.selectedImageIds = [];
          self.previewImage = null;
          self.loadImages();
          self.load();
        });
      });
    },
    confirmDelete: function (ds) {
      var self = this;
      self.$root.confirm({
        title: "删除数据集",
        message: "确定删除数据集「" + ds.name + "」？所有图片和标注将被永久删除。",
        danger: true,
        confirmText: "删除",
      }).then(function (ok) {
        if (!ok) return;
        API.deleteDataset(ds.id).then(function () {
          self.load();
        });
      });
    },
  },
  mounted: function () {
    this.load();
    var self = this;
    this._resizeHandler = function () {
      if (self.previewImage && self.imageLabels.length > 0) {
        self.drawBBoxes();
      }
    };
    window.addEventListener("resize", this._resizeHandler);
  },
  beforeUnmount: function () {
    if (this._resizeHandler) {
      window.removeEventListener("resize", this._resizeHandler);
    }
  },
});
