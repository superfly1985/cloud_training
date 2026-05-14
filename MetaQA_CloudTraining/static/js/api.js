var API = (function () {
  var BASE = "/api/v1";

  function request(method, path, body) {
    var opts = {
      method: method,
      headers: {},
    };
    if (body && !(body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    } else if (body instanceof FormData) {
      opts.body = body;
    }
    return fetch(BASE + path, opts)
      .then(function (res) {
        if (!res.ok && res.status !== 200) {
          return res.json().then(function (err) {
            throw new Error(err.message || err.detail || "请求失败 HTTP " + res.status);
          }).catch(function () {
            throw new Error("请求失败 HTTP " + res.status);
          });
        }
        return res.json();
      })
      .then(function (json) {
        return json;
      });
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + " MB";
    return (bytes / 1073741824).toFixed(1) + " GB";
  }

  var dateFormatter = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  function formatDate(iso) {
    if (!iso) return "-";
    return dateFormatter.format(new Date(iso));
  }

  return {
    formatBytes: formatBytes,
    formatDate: formatDate,

    getDatasets: function () {
      return request("GET", "/datasets");
    },

    getDatasetImages: function (datasetId, page, pageSize) {
      return request("GET", "/datasets/" + datasetId + "/images?page=" + (page || 1) + "&page_size=" + (pageSize || 20));
    },

    createDataset: function (name, splitRatio) {
      return request("POST", "/datasets", { name: name, split_ratio: splitRatio || 0.8 });
    },

    uploadDataset: function (name, splitRatio, file) {
      var formData = new FormData();
      formData.append("name", name);
      formData.append("split_ratio", splitRatio || 0.8);
      formData.append("file", file);
      return request("POST", "/datasets/import", formData);
    },

    deleteDataset: function (datasetId) {
      return request("DELETE", "/datasets/" + datasetId);
    },

    deleteImages: function (datasetId, imageIds) {
      return request("DELETE", "/datasets/" + datasetId + "/images", { image_ids: imageIds });
    },

    getImageLabels: function (datasetId, filename) {
      return request("GET", "/datasets/" + datasetId + "/images/" + encodeURIComponent(filename) + "/labels");
    },

    getTrainingTasks: function () {
      return request("GET", "/training");
    },

    createTraining: function (config) {
      return request("POST", "/training", config);
    },

    stopTraining: function (taskId) {
      return request("POST", "/training/" + taskId + "/stop");
    },

    getTrainingLog: function (taskId) {
      return request("GET", "/training/" + taskId + "/log");
    },

    getLossCurve: function (taskId) {
      return request("GET", "/training/" + taskId + "/curve");
    },

    refreshMetrics: function (taskId) {
      return request("POST", "/training/" + taskId + "/refresh");
    },

    getPackages: function () {
      return request("GET", "/packages");
    },

    getPackageDetail: function (packageId) {
      return request("GET", "/packages/" + packageId);
    },

    createPackage: function (taskId) {
      return request("POST", "/packages", { task_id: taskId });
    },

    deletePackage: function (packageId) {
      return request("DELETE", "/packages/" + packageId);
    },

    downloadPackageUrl: function (packageId) {
      return BASE + "/packages/" + packageId + "/download";
    },

    getSystemStatus: function () {
      return request("GET", "/system/status");
    },

    getSystemChecks: function () {
      return request("GET", "/system/checks");
    },

    fixSystem: function () {
      return request("POST", "/system/fix");
    },

    uploadInit: function (filename, totalSize, chunkSize) {
      return request("POST", "/upload/init", {
        filename: filename,
        total_size: totalSize,
        chunk_size: chunkSize || 5 * 1024 * 1024,
      });
    },

    uploadChunk: function (sessionId, chunkIndex, chunkData) {
      var fd = new FormData();
      fd.append("file", chunkData);
      return fetch(BASE + "/upload/chunk?session_id=" + sessionId + "&chunk_index=" + chunkIndex, {
        method: "POST",
        body: fd,
      }).then(function (res) { return res.json(); });
    },

    uploadComplete: function (sessionId, datasetId, action) {
      return request("POST", "/upload/complete", {
        session_id: sessionId,
        dataset_id: datasetId,
        action: action || "create",
      });
    },
  };
})();
