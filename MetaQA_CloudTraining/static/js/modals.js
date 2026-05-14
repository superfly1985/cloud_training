app.component("confirm-modal", {
  props: ["config"],
  template: `
    <div class="modal-overlay" @click.self="$emit('cancel')" role="dialog" aria-modal="true" :aria-label="config.title">
      <div class="modal-content modal-sm">
        <div class="modal-header">
          <h2>{{ config.title }}</h2>
          <button class="modal-close" @click="$emit('cancel')" aria-label="关闭">
            <i class="bi bi-x-lg" aria-hidden="true"></i>
          </button>
        </div>
        <div class="modal-body">
          <p style="font-size: 14px; color: var(--color-text-secondary);">{{ config.message }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="$emit('cancel')">取消</button>
          <button class="btn" :class="config.danger ? 'btn-danger' : 'btn-primary'" @click="$emit('confirm')">
            {{ config.confirmText || '确认' }}
          </button>
        </div>
      </div>
    </div>
  `,
  mounted: function () {
    var self = this;
    this._keyHandler = function (e) {
      if (e.key === "Escape") self.$emit("cancel");
    };
    document.addEventListener("keydown", this._keyHandler);
    this.$el.querySelector("button").focus();
  },
  beforeUnmount: function () {
    document.removeEventListener("keydown", this._keyHandler);
  },
});

app.component("create-dataset-modal", {
  template: `
    <div class="modal-overlay" :class="{ nobgclose: uploading }" @click.self="canClose ? $emit('close') : null" role="dialog" aria-modal="true" aria-label="创建数据集">
      <div class="modal-content modal-md">
        <div class="modal-header">
          <h2>创建数据集</h2>
          <button v-if="!uploading" class="modal-close" @click="$emit('close')" aria-label="关闭">
            <i class="bi bi-x-lg" aria-hidden="true"></i>
          </button>
        </div>
        <div class="modal-body">
          <p style="font-size: 12px; color: var(--color-text-muted); margin-bottom: 16px;">* 为必填项</p>
          <div class="form-group" v-if="!uploading">
            <label for="ds-name">数据集名称 <span style="color: var(--color-danger);">*</span></label>
            <input id="ds-name" type="text" class="form-control" v-model="name" placeholder="请输入数据集名称…"
                   :class="{ 'is-invalid': errors.name }" @input="errors.name = ''" autocomplete="off" :disabled="uploading">
            <div v-if="errors.name" class="form-error" aria-live="polite">{{ errors.name }}</div>
          </div>
          <div class="form-group" v-if="!uploading">
            <label for="ds-zip">上传 ZIP 文件 <span style="color: var(--color-danger);">*</span></label>
            <input id="ds-zip" type="file" class="form-control" accept=".zip" @change="onFileChange"
                   :class="{ 'is-invalid': errors.file }" :disabled="uploading">
            <div class="form-hint">支持包含图片和标签的 ZIP 文件，最大 2 GB</div>
            <div v-if="errors.file" class="form-error" aria-live="polite">{{ errors.file }}</div>
            <div v-if="fileName" style="margin-top: 8px; font-size: 13px; color: var(--color-success);">
              <i class="bi bi-check-circle" aria-hidden="true"></i> {{ fileName }}
            </div>
          </div>
          <div v-if="!uploading" class="form-hint" style="margin-top: 12px; padding: 10px 12px; background: rgba(37,99,235,0.05); border-radius: var(--radius-sm);">
            训练/验证集分割将在创建训练任务时配置
          </div>

          <div v-if="uploading" class="upload-progress-panel">
            <div style="font-size: 14px; font-weight: 500; margin-bottom: 12px;">
              <span class="spinner"></span> 正在上传 {{ fileName }}
            </div>
            <div class="progress-bar upload-progress-bar">
              <div class="progress-fill" :style="{ width: uploadPercent + '%' }"></div>
            </div>
            <div class="upload-stats">
              <span>{{ uploadPercent }}%</span>
              <span>{{ formatSpeed(uploadSpeed) }}</span>
            </div>
            <div class="upload-stats">
              <span>{{ formatSize(uploadedBytes) }} / {{ formatSize(fileSize) }}</span>
              <span>剩余约 {{ etaText }}</span>
            </div>
            <div v-if="uploadError" class="form-error" style="margin-top: 12px;">{{ uploadError }}</div>
          </div>
        </div>
        <div class="modal-footer">
          <button v-if="!uploading" class="btn btn-ghost" @click="$emit('close')">取消</button>
          <button v-if="uploading" class="btn btn-ghost btn-danger" @click="cancelUpload">取消上传</button>
          <button class="btn btn-primary" @click="submit" :disabled="submitting || uploading">
            <span v-if="submitting" class="spinner"></span>
            {{ uploading ? '上传中…' : submitting ? '创建中…' : '创建' }}
          </button>
        </div>
      </div>
    </div>
  `,
  data: function () {
    return {
      name: "",
      file: null,
      fileName: "",
      fileSize: 0,
      errors: { name: "", file: "" },
      submitting: false,
      uploading: false,
      uploadPercent: 0,
      uploadedBytes: 0,
      uploadSpeed: 0,
      uploadError: "",
      etaText: "…",
      _cancelUpload: false,
      _speedSamples: [],
      _lastTick: 0,
      _lastBytes: 0,
    };
  },
  computed: {
    canClose: function () {
      return !this.uploading;
    },
  },
  methods: {
    formatSize: function (bytes) {
      return API.formatBytes(bytes);
    },
    formatSpeed: function (bps) {
      if (bps < 1024) return bps.toFixed(0) + " B/s";
      if (bps < 1048576) return (bps / 1024).toFixed(1) + " KB/s";
      return (bps / 1048576).toFixed(1) + " MB/s";
    },
    onFileChange: function (e) {
      var f = e.target.files[0];
      if (f) {
        this.file = f;
        this.fileName = f.name;
        this.fileSize = f.size;
        this.errors.file = "";
      }
    },
    submit: function () {
      var valid = true;
      if (!this.name.trim()) {
        this.errors.name = "请输入数据集名称";
        valid = false;
      }
      if (!this.file) {
        this.errors.file = "请选择 ZIP 文件";
        valid = false;
      }
      if (!valid) return;

      var self = this;
      self.submitting = true;
      self._doChunkedUpload(self.name, self.file, null);
    },
    cancelUpload: function () {
      this._cancelUpload = true;
    },
    _doChunkedUpload: function (dsName, file, targetDsId) {
      var self = this;
      var chunkSize = 5 * 1024 * 1024;
      var totalSize = file.size;
      var totalChunks = Math.ceil(totalSize / chunkSize);

      self.uploading = true;
      self.uploadPercent = 0;
      self.uploadedBytes = 0;
      self.uploadSpeed = 0;
      self.uploadError = "";
      self.etaText = "计算中…";
      self._cancelUpload = false;
      self._speedSamples = [];
      self._lastTick = 0;
      self._lastBytes = 0;

      API.uploadInit(file.name, totalSize, chunkSize).then(function (res) {
        if (res.code !== 0 || self._cancelUpload) {
          self.uploading = false;
          self.submitting = false;
          self.uploadError = res.message || "初始化上传失败";
          return;
        }
        var sessionId = res.data.session_id;
        self._lastTick = Date.now();
        self._lastBytes = 0;
        self._uploadChunks(sessionId, file, 0, totalChunks, chunkSize, targetDsId);
      }).catch(function (err) {
        self.uploading = false;
        self.submitting = false;
        self.uploadError = "网络错误: " + (err.message || "初始化失败");
      });
    },
    _uploadChunks: function (sessionId, file, idx, total, chunkSize, targetDsId) {
      var self = this;
      if (self._cancelUpload) {
        self.uploading = false;
        self.submitting = false;
        return;
      }

      if (idx >= total) {
        self._finishUpload(sessionId, targetDsId);
        return;
      }

      var start = idx * chunkSize;
      var end = Math.min(start + chunkSize, file.size);
      var blob = file.slice(start, end);

      API.uploadChunk(sessionId, idx, blob).then(function (res) {
        if (res.code !== 0) {
          self.uploading = false;
          self.submitting = false;
          self.uploadError = res.message || "上传分片失败";
          return;
        }

        var now = Date.now();
        self.uploadedBytes = Math.min(end, file.size);
        self.uploadPercent = Math.min(100, Math.round((self.uploadedBytes / file.size) * 100));

        var elapsed = (now - self._lastTick) / 1000;
        var bytesDelta = self.uploadedBytes - self._lastBytes;
        if (elapsed > 0 && bytesDelta > 0) {
          var instantSpeed = bytesDelta / elapsed;
          self._speedSamples.push(instantSpeed);
          if (self._speedSamples.length > 8) self._speedSamples.shift();
          var sum = 0;
          for (var i = 0; i < self._speedSamples.length; i++) sum += self._speedSamples[i];
          self.uploadSpeed = sum / self._speedSamples.length;
          self._lastTick = now;
          self._lastBytes = self.uploadedBytes;

          var remaining = file.size - self.uploadedBytes;
          var etaSec = self.uploadSpeed > 0 ? Math.ceil(remaining / self.uploadSpeed) : 0;
          if (etaSec < 60) self.etaText = etaSec + " 秒";
          else if (etaSec < 3600) self.etaText = Math.floor(etaSec / 60) + " 分 " + (etaSec % 60) + " 秒";
          else self.etaText = Math.floor(etaSec / 3600) + " 时 " + Math.floor((etaSec % 3600) / 60) + " 分";
        }

        self._uploadChunks(sessionId, file, idx + 1, total, chunkSize, targetDsId);
      }).catch(function (err) {
        self.uploading = false;
        self.submitting = false;
        self.uploadError = "网络错误: " + (err.message || "上传中断");
      });
    },
    _finishUpload: function (sessionId, targetDsId) {
      var self = this;
      API.uploadComplete(sessionId, targetDsId, targetDsId ? "merge" : "create").then(function (res) {
        self.uploading = false;
        self.submitting = false;
        if (res.code !== 0) {
          self.uploadError = res.message || "导入失败";
          return;
        }
        self.$emit("close");
      }).catch(function (err) {
        self.uploading = false;
        self.submitting = false;
        self.uploadError = "导入失败: " + (err.message || "请重试");
      });
    },
  },
  mounted: function () {
    var self = this;
    this._keyHandler = function (e) {
      if (e.key === "Escape" && !self.uploading) self.$emit("close");
    };
    document.addEventListener("keydown", this._keyHandler);
  },
  beforeUnmount: function () {
    document.removeEventListener("keydown", this._keyHandler);
  },
});

app.component("merge-dataset-modal", {
  template: `
    <div class="modal-overlay" :class="{ nobgclose: uploading }" @click.self="canClose ? $emit('close') : null" role="dialog" aria-modal="true" aria-label="合并新增数据">
      <div class="modal-content modal-md">
        <div class="modal-header">
          <h2>合并新增数据</h2>
          <button v-if="!uploading" class="modal-close" @click="$emit('close')" aria-label="关闭">
            <i class="bi bi-x-lg" aria-hidden="true"></i>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group" v-if="!uploading">
            <label for="merge-target">目标数据集 <span style="color: var(--color-danger);">*</span></label>
            <select id="merge-target" class="form-control" v-model="targetId" :disabled="uploading">
              <option value="">请选择目标数据集…</option>
              <option v-for="ds in datasets" :key="ds.id" :value="ds.id">{{ ds.name }} ({{ ds.image_count }} 张)</option>
            </select>
          </div>
          <div class="form-group" v-if="!uploading">
            <label for="merge-zip">上传新增数据 ZIP <span style="color: var(--color-danger);">*</span></label>
            <input id="merge-zip" type="file" class="form-control" accept=".zip" @change="onFileChange" :disabled="uploading">
            <div class="form-hint">新增数据将合并到目标数据集中</div>
            <div v-if="fileName" style="margin-top: 8px; font-size: 13px; color: var(--color-success);">
              <i class="bi bi-check-circle" aria-hidden="true"></i> {{ fileName }}
            </div>
          </div>

          <div v-if="uploading" class="upload-progress-panel">
            <div style="font-size: 14px; font-weight: 500; margin-bottom: 12px;">
              <span class="spinner"></span> 正在上传 {{ fileName }}
            </div>
            <div class="progress-bar upload-progress-bar">
              <div class="progress-fill" :style="{ width: uploadPercent + '%' }"></div>
            </div>
            <div class="upload-stats">
              <span>{{ uploadPercent }}%</span>
              <span>{{ formatSpeed(uploadSpeed) }}</span>
            </div>
            <div class="upload-stats">
              <span>{{ formatSize(uploadedBytes) }} / {{ formatSize(fileSize) }}</span>
              <span>剩余约 {{ etaText }}</span>
            </div>
            <div v-if="uploadError" class="form-error" style="margin-top: 12px;">{{ uploadError }}</div>
          </div>
        </div>
        <div class="modal-footer">
          <button v-if="!uploading" class="btn btn-ghost" @click="$emit('close')">取消</button>
          <button v-if="uploading" class="btn btn-ghost btn-danger" @click="cancelUpload">取消上传</button>
          <button class="btn btn-primary" @click="submit" :disabled="!targetId || !file || submitting || uploading">
            <span v-if="submitting" class="spinner"></span>
            {{ uploading ? '上传中…' : submitting ? '合并中…' : '合并' }}
          </button>
        </div>
      </div>
    </div>
  `,
  data: function () {
    return {
      datasets: [],
      targetId: "",
      file: null,
      fileName: "",
      fileSize: 0,
      submitting: false,
      uploading: false,
      uploadPercent: 0,
      uploadedBytes: 0,
      uploadSpeed: 0,
      uploadError: "",
      etaText: "…",
      _cancelUpload: false,
      _speedSamples: [],
      _lastTick: 0,
      _lastBytes: 0,
    };
  },
  computed: {
    canClose: function () {
      return !this.uploading;
    },
  },
  methods: {
    formatSize: function (bytes) {
      return API.formatBytes(bytes);
    },
    formatSpeed: function (bps) {
      if (bps < 1024) return bps.toFixed(0) + " B/s";
      if (bps < 1048576) return (bps / 1024).toFixed(1) + " KB/s";
      return (bps / 1048576).toFixed(1) + " MB/s";
    },
    onFileChange: function (e) {
      var f = e.target.files[0];
      if (f) {
        this.file = f;
        this.fileName = f.name;
        this.fileSize = f.size;
      }
    },
    submit: function () {
      if (!this.targetId || !this.file) return;
      var self = this;
      self.submitting = true;
      self._doChunkedUpload(self.file, self.targetId);
    },
    cancelUpload: function () {
      this._cancelUpload = true;
    },
    _doChunkedUpload: function (file, targetDsId) {
      var self = this;
      var chunkSize = 5 * 1024 * 1024;
      var totalSize = file.size;
      var totalChunks = Math.ceil(totalSize / chunkSize);

      self.uploading = true;
      self.uploadPercent = 0;
      self.uploadedBytes = 0;
      self.uploadSpeed = 0;
      self.uploadError = "";
      self.etaText = "计算中…";
      self._cancelUpload = false;
      self._speedSamples = [];
      self._lastTick = 0;
      self._lastBytes = 0;

      API.uploadInit(file.name, totalSize, chunkSize).then(function (res) {
        if (res.code !== 0 || self._cancelUpload) {
          self.uploading = false;
          self.submitting = false;
          self.uploadError = res.message || "初始化上传失败";
          return;
        }
        var sessionId = res.data.session_id;
        self._lastTick = Date.now();
        self._lastBytes = 0;
        self._uploadChunks(sessionId, file, 0, totalChunks, chunkSize, targetDsId);
      }).catch(function (err) {
        self.uploading = false;
        self.submitting = false;
        self.uploadError = "网络错误: " + (err.message || "初始化失败");
      });
    },
    _uploadChunks: function (sessionId, file, idx, total, chunkSize, targetDsId) {
      var self = this;
      if (self._cancelUpload) {
        self.uploading = false;
        self.submitting = false;
        return;
      }

      if (idx >= total) {
        self._finishUpload(sessionId, targetDsId);
        return;
      }

      var start = idx * chunkSize;
      var end = Math.min(start + chunkSize, file.size);
      var blob = file.slice(start, end);

      API.uploadChunk(sessionId, idx, blob).then(function (res) {
        if (res.code !== 0) {
          self.uploading = false;
          self.submitting = false;
          self.uploadError = res.message || "上传分片失败";
          return;
        }

        var now = Date.now();
        self.uploadedBytes = Math.min(end, file.size);
        self.uploadPercent = Math.min(100, Math.round((self.uploadedBytes / file.size) * 100));

        var elapsed = (now - self._lastTick) / 1000;
        var bytesDelta = self.uploadedBytes - self._lastBytes;
        if (elapsed > 0 && bytesDelta > 0) {
          var instantSpeed = bytesDelta / elapsed;
          self._speedSamples.push(instantSpeed);
          if (self._speedSamples.length > 8) self._speedSamples.shift();
          var sum = 0;
          for (var i = 0; i < self._speedSamples.length; i++) sum += self._speedSamples[i];
          self.uploadSpeed = sum / self._speedSamples.length;
          self._lastTick = now;
          self._lastBytes = self.uploadedBytes;

          var remaining = file.size - self.uploadedBytes;
          var etaSec = self.uploadSpeed > 0 ? Math.ceil(remaining / self.uploadSpeed) : 0;
          if (etaSec < 60) self.etaText = etaSec + " 秒";
          else if (etaSec < 3600) self.etaText = Math.floor(etaSec / 60) + " 分 " + (etaSec % 60) + " 秒";
          else self.etaText = Math.floor(etaSec / 3600) + " 时 " + Math.floor((etaSec % 3600) / 60) + " 分";
        }

        self._uploadChunks(sessionId, file, idx + 1, total, chunkSize, targetDsId);
      }).catch(function (err) {
        self.uploading = false;
        self.submitting = false;
        self.uploadError = "网络错误: " + (err.message || "上传中断");
      });
    },
    _finishUpload: function (sessionId, targetDsId) {
      var self = this;
      API.uploadComplete(sessionId, targetDsId, "merge").then(function (res) {
        self.uploading = false;
        self.submitting = false;
        if (res.code !== 0) {
          self.uploadError = res.message || "合并失败";
          return;
        }
        self.$emit("close");
      }).catch(function (err) {
        self.uploading = false;
        self.submitting = false;
        self.uploadError = "合并失败: " + (err.message || "请重试");
      });
    },
  },
  mounted: function () {
    var self = this;
    API.getDatasets().then(function (res) {
      self.datasets = res.data.datasets;
    });
    this._keyHandler = function (e) {
      if (e.key === "Escape" && !self.uploading) self.$emit("close");
    };
    document.addEventListener("keydown", this._keyHandler);
  },
  beforeUnmount: function () {
    document.removeEventListener("keydown", this._keyHandler);
  },
});

app.component("new-training-modal", {
  template: `
    <div class="modal-overlay" @click.self="$emit('close')" role="dialog" aria-modal="true" aria-label="新建训练任务">
      <div class="modal-content modal-lg">
        <div class="modal-header">
          <h2>新建训练任务</h2>
          <button class="modal-close" @click="$emit('close')" aria-label="关闭">
            <i class="bi bi-x-lg" aria-hidden="true"></i>
          </button>
        </div>
        <div class="modal-body">
          <p style="font-size: 12px; color: var(--color-text-muted); margin-bottom: 16px;">* 为必填项</p>
          <div class="form-row">
            <div class="form-group">
              <label for="train-dataset">数据集 <span style="color: var(--color-danger);">*</span></label>
              <select id="train-dataset" class="form-control" v-model="form.dataset_id"
                      :class="{ 'is-invalid': errors.dataset_id }" @change="errors.dataset_id = ''">
                <option value="">请选择数据集…</option>
                <option v-for="ds in datasets" :key="ds.id" :value="ds.id">{{ ds.name }} ({{ ds.image_count }} 张)</option>
              </select>
              <div v-if="errors.dataset_id" class="form-error" aria-live="polite">{{ errors.dataset_id }}</div>
            </div>
            <div class="form-group">
              <label for="train-model">模型大小 <span style="color: var(--color-danger);">*</span></label>
              <select id="train-model" class="form-control" v-model="form.model_size">
                <option value="n">YOLOv8n (最快)</option>
                <option value="s">YOLOv8s (平衡)</option>
                <option value="m">YOLOv8m (中等)</option>
                <option value="l">YOLOv8l (高精度)</option>
              </select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label for="train-split">训练/验证集分割比例</label>
              <select id="train-split" class="form-control" v-model.number="form.split_ratio">
                <option :value="0.8">80% 训练 / 20% 验证</option>
                <option :value="0.9">90% 训练 / 10% 验证</option>
                <option :value="0.7">70% 训练 / 30% 验证</option>
              </select>
            </div>
            <div class="form-group">
              <label for="train-epochs">训练轮次 <span style="color: var(--color-danger);">*</span></label>
              <input id="train-epochs" type="number" class="form-control" v-model.number="form.epochs" min="1" max="1000"
                     :class="{ 'is-invalid': errors.epochs }" @input="errors.epochs = ''" autocomplete="off">
              <div v-if="errors.epochs" class="form-error" aria-live="polite">{{ errors.epochs }}</div>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label for="train-batch">批大小</label>
              <select id="train-batch" class="form-control" v-model="form.batch_size">
                <option :value="8">8</option>
                <option :value="16">16</option>
                <option :value="32">32</option>
                <option :value="64">64</option>
              </select>
            </div>
            <div class="form-group">
              <label for="train-input">输入尺寸</label>
              <select id="train-input" class="form-control" v-model="form.input_size">
                <option :value="640">640</option>
                <option :value="1280">1280</option>
              </select>
            </div>
            <div class="form-group">
              <label for="train-lr">学习率</label>
              <input id="train-lr" type="number" class="form-control" v-model="form.learning_rate" step="0.001" min="0.0001" max="1" autocomplete="off">
            </div>
          </div>
          <div class="form-group">
            <label for="train-device">训练设备</label>
            <select id="train-device" class="form-control" v-model="form.device">
              <option value="cuda:0">GPU (cuda:0)</option>
              <option value="cpu">CPU</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="$emit('close')">取消</button>
          <button class="btn btn-primary" @click="submit" :disabled="submitting">
            <span v-if="submitting" class="spinner"></span>
            {{ submitting ? '启动中…' : '开始训练' }}
          </button>
        </div>
      </div>
    </div>
  `,
  data: function () {
    return {
      datasets: [],
      form: {
        dataset_id: "",
        model_size: "n",
        split_ratio: 0.8,
        epochs: 100,
        batch_size: 16,
        input_size: 640,
        learning_rate: 0.01,
        device: "cuda:0",
      },
      errors: { dataset_id: "", epochs: "" },
      submitting: false,
    };
  },
  methods: {
    submit: function () {
      var valid = true;
      if (!this.form.dataset_id) {
        this.errors.dataset_id = "请选择数据集";
        valid = false;
      }
      if (!this.form.epochs || this.form.epochs < 1) {
        this.errors.epochs = "训练轮次必须大于 0";
        valid = false;
      }
      if (!valid) return;

      var self = this;
      self.submitting = true;
      API.createTraining(self.form).then(function () {
        self.submitting = false;
        self.$emit("close");
      });
    },
  },
  mounted: function () {
    var self = this;
    API.getDatasets().then(function (res) {
      self.datasets = res.data.datasets;
    });
    this._keyHandler = function (e) {
      if (e.key === "Escape") self.$emit("close");
    };
    document.addEventListener("keydown", this._keyHandler);
  },
  beforeUnmount: function () {
    document.removeEventListener("keydown", this._keyHandler);
  },
});

app.component("training-log-modal", {
  props: ["taskId"],
  template: `
    <div class="modal-overlay" @click.self="$emit('close')" role="dialog" aria-modal="true" aria-label="训练日志">
      <div class="modal-content modal-lg">
        <div class="modal-header">
          <h2>训练日志</h2>
          <button class="modal-close" @click="$emit('close')" aria-label="关闭">
            <i class="bi bi-x-lg" aria-hidden="true"></i>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="loading" style="text-align: center; padding: 40px; color: var(--color-text-muted);" aria-live="polite">
            加载中…
          </div>
          <div v-else class="log-container" ref="logContainer">
            <div v-for="(line, i) in logLines" :key="i" class="log-line">{{ line }}</div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="$emit('close')">关闭</button>
        </div>
      </div>
    </div>
  `,
  data: function () {
    return {
      logLines: [],
      loading: true,
    };
  },
  methods: {
    loadLog: function () {
      var self = this;
      self.loading = true;
      API.getTrainingLog(self.taskId).then(function (res) {
        self.logLines = res.data.log.split("\n");
        self.loading = false;
        self.$nextTick(function () {
          if (self.$refs.logContainer) {
            self.$refs.logContainer.scrollTop = self.$refs.logContainer.scrollHeight;
          }
        });
      });
    },
  },
  watch: {
    taskId: function () {
      if (this.taskId) this.loadLog();
    },
  },
  mounted: function () {
    this.loadLog();
    this._keyHandler = function (e) {
      if (e.key === "Escape") this.$emit("close");
    }.bind(this);
    document.addEventListener("keydown", this._keyHandler);
  },
  beforeUnmount: function () {
    document.removeEventListener("keydown", this._keyHandler);
  },
});

app.component("training-chart-modal", {
  props: ["taskId"],
  template: `
    <div class="modal-overlay" @click.self="$emit('close')" role="dialog" aria-modal="true" aria-label="损失曲线">
      <div class="modal-content modal-lg">
        <div class="modal-header">
          <h2>损失曲线</h2>
          <button class="modal-close" @click="$emit('close')" aria-label="关闭">
            <i class="bi bi-x-lg" aria-hidden="true"></i>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="loading" style="text-align: center; padding: 40px; color: var(--color-text-muted);" aria-live="polite">
            加载中…
          </div>
          <canvas v-else ref="chartCanvas" width="760" height="400"></canvas>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="$emit('close')">关闭</button>
        </div>
      </div>
    </div>
  `,
  data: function () {
    return {
      loading: true,
      chartInstance: null,
    };
  },
  methods: {
    loadChart: function () {
      var self = this;
      self.loading = true;
      API.getLossCurve(self.taskId).then(function (res) {
        self.loading = false;
        self.$nextTick(function () {
          self.drawChart(res.data);
        });
      });
    },
    drawChart: function (data) {
      var canvas = this.$refs.chartCanvas;
      if (!canvas) return;
      var ctx = canvas.getContext("2d");
      var w = canvas.width;
      var h = canvas.height;
      var pad = { top: 30, right: 30, bottom: 40, left: 60 };
      var cw = w - pad.left - pad.right;
      var ch = h - pad.top - pad.bottom;

      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, w, h);

      var allVals = data.box_loss.concat(data.cls_loss, data.map50);
      var minV = Math.min.apply(null, allVals);
      var maxV = Math.max.apply(null, allVals);
      var range = maxV - minV || 1;
      minV -= range * 0.05;
      maxV += range * 0.05;
      range = maxV - minV;

      ctx.strokeStyle = "#e5e7eb";
      ctx.lineWidth = 1;
      for (var i = 0; i <= 5; i++) {
        var y = pad.top + (ch * i) / 5;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(w - pad.right, y);
        ctx.stroke();
        ctx.fillStyle = "#9ca3af";
        ctx.font = "11px system-ui";
        ctx.textAlign = "right";
        ctx.fillText((maxV - (range * i) / 5).toFixed(3), pad.left - 8, y + 4);
      }

      ctx.fillStyle = "#6b7280";
      ctx.font = "12px system-ui";
      ctx.textAlign = "center";
      var step = Math.max(1, Math.floor(data.epochs.length / 6));
      for (var i = 0; i < data.epochs.length; i += step) {
        var x = pad.left + (cw * i) / (data.epochs.length - 1);
        ctx.fillText(data.epochs[i], x, h - pad.bottom + 20);
      }

      var series = [
        { data: data.box_loss, color: "#2563eb", label: "Box Loss" },
        { data: data.cls_loss, color: "#dc2626", label: "Cls Loss" },
        { data: data.map50, color: "#16a34a", label: "mAP@50" },
      ];

      series.forEach(function (s) {
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        s.data.forEach(function (v, i) {
          var x = pad.left + (cw * i) / (data.epochs.length - 1);
          var y = pad.top + ch - ((v - minV) / range) * ch;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
      });

      var legendY = 12;
      var legendX = pad.left;
      series.forEach(function (s) {
        ctx.fillStyle = s.color;
        ctx.fillRect(legendX, legendY, 16, 3);
        ctx.fillStyle = "#374151";
        ctx.font = "12px system-ui";
        ctx.textAlign = "left";
        ctx.fillText(s.label, legendX + 20, legendY + 5);
        legendX += 100;
      });
    },
  },
  watch: {
    taskId: function () {
      if (this.taskId) this.loadChart();
    },
  },
  mounted: function () {
    this.loadChart();
    this._keyHandler = function (e) {
      if (e.key === "Escape") this.$emit("close");
    }.bind(this);
    document.addEventListener("keydown", this._keyHandler);
  },
  beforeUnmount: function () {
    document.removeEventListener("keydown", this._keyHandler);
  },
});

app.component("package-detail-modal", {
  props: ["packageId"],
  template: `
    <div class="modal-overlay" @click.self="$emit('close')" role="dialog" aria-modal="true" aria-label="产物包详情">
      <div class="modal-content modal-md">
        <div class="modal-header">
          <h2>产物包详情</h2>
          <button class="modal-close" @click="$emit('close')" aria-label="关闭">
            <i class="bi bi-x-lg" aria-hidden="true"></i>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="loading" style="text-align: center; padding: 40px; color: var(--color-text-muted);" aria-live="polite">
            加载中…
          </div>
          <template v-else-if="pkg">
            <div style="margin-bottom: 16px;">
              <div style="font-size: 16px; font-weight: 600;">{{ pkg.name }}</div>
              <div style="font-size: 13px; color: var(--color-text-secondary);">{{ pkg.dataset_name }} · {{ pkg.version }}</div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
              <div>
                <div style="font-size: 12px; color: var(--color-text-muted);">mAP@50</div>
                <div style="font-size: 18px; font-weight: 600;" class="numeric">{{ pkg.map_val.toFixed(4) }}</div>
              </div>
              <div>
                <div style="font-size: 12px; color: var(--color-text-muted);">训练时长</div>
                <div style="font-size: 18px; font-weight: 600;">{{ pkg.training_time }}</div>
              </div>
            </div>
            <div class="card-title" style="margin-bottom: 8px;">包含文件</div>
            <div v-if="pkg.files && pkg.files.length > 0">
              <div v-for="f in pkg.files" :key="f.name" style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--color-border);">
                <span>{{ f.name }}</span>
                <span class="numeric" style="color: var(--color-text-secondary);">{{ formatSize(f.size) }}</span>
              </div>
            </div>
            <div v-else style="color: var(--color-text-muted);">暂无文件信息</div>
          </template>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="$emit('close')">关闭</button>
          <button v-if="pkg" class="btn btn-primary" @click="download">
            <i class="bi bi-download" aria-hidden="true"></i> 下载
          </button>
        </div>
      </div>
    </div>
  `,
  data: function () {
    return {
      pkg: null,
      loading: true,
    };
  },
  methods: {
    formatSize: function (bytes) {
      return API.formatBytes(bytes);
    },
    loadDetail: function () {
      var self = this;
      self.loading = true;
      API.getPackageDetail(self.packageId).then(function (res) {
        self.pkg = res.data;
        self.loading = false;
      });
    },
    download: function () {
      if (!this.pkg) return;
      var url = API.downloadPackageUrl(this.pkg.id);
      var a = document.createElement("a");
      a.href = url;
      a.download = this.pkg.name;
      a.click();
    },
  },
  watch: {
    packageId: function () {
      if (this.packageId) this.loadDetail();
    },
  },
  mounted: function () {
    this.loadDetail();
    this._keyHandler = function (e) {
      if (e.key === "Escape") this.$emit("close");
    }.bind(this);
    document.addEventListener("keydown", this._keyHandler);
  },
  beforeUnmount: function () {
    document.removeEventListener("keydown", this._keyHandler);
  },
});
