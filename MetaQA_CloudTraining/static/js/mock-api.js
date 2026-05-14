var MockAPI = (function () {
  var dsNames = [
    "焊点漏包", "大小支架V2", "螺丝缺陷", "PCB焊盘", "电容偏移",
    "芯片引脚", "排线接口", "外壳划痕", "密封圈", "弹簧变形",
    "齿轮磨损", "轴承裂纹", "线束端子", "插针弯曲", "胶水溢出",
    "标签偏移", "锡珠残留", "铜箔断裂", "阻焊层", "丝印模糊",
    "导通孔堵塞", "金手指氧化", "BGA气泡", "贴片偏移", "极性反接",
    "绝缘破损", "散热片松动", "螺丝滑丝", "卡扣断裂", "焊桥短路",
    "针脚缺失", "表面脏污", "尺寸超差", "颜色异常", "纹理缺陷",
    "气泡孔洞", "毛刺飞边", "装配错位", "漏装零件", "错装零件",
    "压痕凹陷", "镀层脱落", "氧化锈蚀", "变形翘曲", "裂纹断裂",
    "异物残留", "印刷模糊", "接缝不齐", "粘合不良", "涂层不均"
  ];

  var classPool = [
    [{id: "0", name: "漏包"}], [{id: "0", name: "大支架"}, {id: "1", name: "小支架"}], [{id: "0", name: "滑丝"}, {id: "1", name: "歪斜"}, {id: "2", name: "缺失"}],
    [{id: "0", name: "焊盘缺失"}, {id: "1", name: "焊盘偏移"}], [{id: "0", name: "偏移"}, {id: "1", name: "缺失"}], [{id: "0", name: "引脚弯曲"}, {id: "1", name: "引脚短路"}],
    [{id: "0", name: "接口松动"}, {id: "1", name: "接口损坏"}], [{id: "0", name: "划痕"}, {id: "1", name: "凹陷"}], [{id: "0", name: "变形"}, {id: "1", name: "断裂"}],
    [{id: "0", name: "变形"}, {id: "1", name: "疲劳"}], [{id: "0", name: "磨损"}, {id: "1", name: "崩齿"}], [{id: "0", name: "裂纹"}, {id: "1", name: "剥落"}],
    [{id: "0", name: "端子松动"}, {id: "1", name: "端子氧化"}], [{id: "0", name: "弯曲"}, {id: "1", name: "断裂"}], [{id: "0", name: "溢出"}, {id: "1", name: "缺失"}],
    [{id: "0", name: "偏移"}, {id: "1", name: "倾斜"}], [{id: "0", name: "残留"}, {id: "1", name: "桥接"}], [{id: "0", name: "断裂"}, {id: "1", name: "缺损"}],
    [{id: "0", name: "缺损"}, {id: "1", name: "起泡"}], [{id: "0", name: "模糊"}, {id: "1", name: "缺失"}], [{id: "0", name: "堵塞"}, {id: "1", name: "偏移"}],
    [{id: "0", name: "氧化"}, {id: "1", name: "磨损"}], [{id: "0", name: "气泡"}, {id: "1", name: "空洞"}], [{id: "0", name: "偏移"}, {id: "1", name: "翻转"}],
    [{id: "0", name: "反接"}, {id: "1", name: "短路"}], [{id: "0", name: "破损"}, {id: "1", name: "老化"}], [{id: "0", name: "松动"}, {id: "1", name: "倾斜"}],
    [{id: "0", name: "滑丝"}, {id: "1", name: "卡死"}], [{id: "0", name: "断裂"}, {id: "1", name: "变形"}], [{id: "0", name: "短路"}, {id: "1", name: "桥接"}],
    [{id: "0", name: "缺失"}, {id: "1", name: "弯曲"}], [{id: "0", name: "脏污"}, {id: "1", name: "油渍"}], [{id: "0", name: "超差"}, {id: "1", name: "变形"}],
    [{id: "0", name: "异常"}, {id: "1", name: "褪色"}], [{id: "0", name: "缺陷"}, {id: "1", name: "不均"}], [{id: "0", name: "孔洞"}, {id: "1", name: "气泡"}],
    [{id: "0", name: "毛刺"}, {id: "1", name: "飞边"}], [{id: "0", name: "错位"}, {id: "1", name: "偏移"}], [{id: "0", name: "漏装"}, {id: "1", name: "缺件"}],
    [{id: "0", name: "错装"}, {id: "1", name: "多装"}], [{id: "0", name: "凹陷"}, {id: "1", name: "压痕"}], [{id: "0", name: "脱落"}, {id: "1", name: "起皮"}],
    [{id: "0", name: "锈蚀"}, {id: "1", name: "氧化"}], [{id: "0", name: "翘曲"}, {id: "1", name: "扭曲"}], [{id: "0", name: "裂纹"}, {id: "1", name: "断裂"}],
    [{id: "0", name: "异物"}, {id: "1", name: "残留"}], [{id: "0", name: "模糊"}, {id: "1", name: "重影"}], [{id: "0", name: "不齐"}, {id: "1", name: "错位"}],
    [{id: "0", name: "脱胶"}, {id: "1", name: "起泡"}], [{id: "0", name: "不均"}, {id: "1", name: "漏涂"}]
  ];

  var modelSizes = ["n", "s", "m", "l"];
  var statusPool = ["running", "completed", "stopped", "failed"];

  var datasets = [];
  for (var i = 0; i < 50; i++) {
    var imgCount = Math.floor(Math.random() * 1500) + 200;
    var annRate = 0.7 + Math.random() * 0.3;
    var annCount = Math.floor(imgCount * annRate);
    var dayOffset = Math.floor(i * 0.6);
    var created = new Date(2026, 4, 13 - dayOffset, 8 + (i % 12), i % 60, 0);
    datasets.push({
      id: "ds-" + String(i + 1).padStart(3, "0"),
      name: dsNames[i],
      image_count: imgCount,
      annotated_count: annCount,
      classes: classPool[i % classPool.length],
      total_size: Math.floor(imgCount * (300000 + Math.random() * 500000)),
      created_at: created.toISOString(),
      updated_at: new Date(created.getTime() + (i % 5) * 86400000).toISOString(),
    });
  }

  var trainingTasks = [];
  for (var i = 0; i < 50; i++) {
    var dsIdx = i % 50;
    var ds = datasets[dsIdx];
    var verNum = Math.floor(i / 50) + 1;
    var status = statusPool[i % 4];
    var epochs = [50, 80, 100, 150, 200][i % 5];
    var current = status === "completed" ? epochs : status === "running" ? Math.floor(Math.random() * epochs * 0.8) + 1 : status === "failed" ? Math.floor(Math.random() * epochs * 0.3) + 1 : Math.floor(Math.random() * epochs * 0.6) + 1;
    var baseMap = 0.6 + Math.random() * 0.35;
    var dayOffset = Math.floor(i * 0.5);
    var created = new Date(2026, 4, 13 - dayOffset, 8 + (i % 14), i % 60, 0);
    trainingTasks.push({
      id: "task-" + String(i + 1).padStart(3, "0"),
      dataset_name: ds.name,
      dataset_id: ds.id,
      version: "v" + String(verNum).padStart(3, "0"),
      model_size: modelSizes[i % 4],
      input_size: i % 3 === 0 ? 1280 : 640,
      epochs: epochs,
      current_epoch: current,
      batch_size: [8, 16, 32][i % 3],
      learning_rate: [0.001, 0.005, 0.01][i % 3],
      device: "cuda:0",
      status: status,
      map50: current > 0 ? +(baseMap * (current / epochs) * 1.1).toFixed(4) : 0,
      map50_95: current > 0 ? +(baseMap * (current / epochs) * 0.75).toFixed(4) : 0,
      box_loss: current > 0 ? +(0.5 - (current / epochs) * 0.3 + Math.random() * 0.05).toFixed(3) : 0,
      cls_loss: current > 0 ? +(0.4 - (current / epochs) * 0.25 + Math.random() * 0.03).toFixed(3) : 0,
      created_at: created.toISOString(),
      started_at: new Date(created.getTime() + 60000).toISOString(),
      completed_at: status === "completed" ? new Date(created.getTime() + 7200000 + Math.random() * 3600000).toISOString() : undefined,
    });
  }

  var packages = [];
  for (var i = 0; i < 50; i++) {
    var task = trainingTasks[i];
    var pkgSize = Math.floor(10000000 + Math.random() * 15000000);
    var mapVal = task.status === "completed" ? task.map50 : 0.5 + Math.random() * 0.45;
    var hours = Math.floor(Math.random() * 4) + 1;
    var mins = Math.floor(Math.random() * 59);
    var dayOffset = Math.floor(i * 0.4);
    var created = new Date(2026, 4, 13 - dayOffset, 10 + (i % 12), i % 60, 0);
    packages.push({
      id: "pkg-" + String(i + 1).padStart(3, "0"),
      name: task.dataset_name + "_" + task.version + ".zip",
      dataset_name: task.dataset_name,
      version: task.version,
      size: pkgSize,
      map: +mapVal.toFixed(4),
      training_time: hours + "h " + (mins < 10 ? "0" : "") + mins + "m",
      created_at: created.toISOString(),
      files: [
        { name: "best.pt", size: Math.floor(pkgSize * 0.65) },
        { name: "best.onnx", size: Math.floor(pkgSize * 0.42) },
        { name: "best_fp16.tflite", size: Math.floor(pkgSize * 0.22) },
        { name: "best_fp32.tflite", size: Math.floor(pkgSize * 0.44) },
        { name: "results.csv", size: Math.floor(15000 + Math.random() * 10000) },
        { name: "dataset.yaml", size: 10000 },
        { name: "info.json", size: 10000 },
      ],
    });
  }

  var imagesCache = {};

  function getImagesForDataset(datasetId) {
    if (imagesCache[datasetId]) return imagesCache[datasetId];
    var ds = datasets.find(function (d) { return d.id === datasetId; });
    if (!ds) return [];
    var list = [];
    for (var i = 1; i <= ds.image_count; i++) {
      list.push({
        id: ds.id + "-img-" + i,
        filename: "img_" + String(i).padStart(4, "0") + ".jpg",
        size: Math.floor(Math.random() * 512000) + 128000,
        width: 800,
        height: 600,
        annotated: i <= ds.annotated_count,
        thumbnail_url:
          "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='48' height='48'%3E%3Crect fill='%23e5e7eb' width='48' height='48'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-size='10' fill='%239ca3af'%3E" +
          i +
          "%3C/text%3E%3C/svg%3E",
      });
    }
    imagesCache[datasetId] = list;
    return list;
  }

  var systemChecks = [
    { name: "Python 环境", status: "pass", message: "Python 3.10.12 已安装", auto_fixable: false },
    { name: "CUDA 驱动", status: "pass", message: "CUDA 11.8 已安装", auto_fixable: false },
    { name: "GPU 可用性", status: "pass", message: "NVIDIA RTX 4090 可访问", auto_fixable: false },
    { name: "Ultralytics", status: "pass", message: "ultralytics 8.0.200 已安装", auto_fixable: true },
    { name: "ONNX", status: "pass", message: "onnx 1.15.0 已安装", auto_fixable: true },
    { name: "TFLite 依赖", status: "pass", message: "tensorflow-lite 2.13.0 可用", auto_fixable: true },
    { name: "磁盘空间", status: "pass", message: "可用 300 GB", auto_fixable: false },
    { name: "数据集目录", status: "pass", message: "已存在", auto_fixable: true },
  ];

  function delay(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms || 300);
    });
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return new Intl.NumberFormat("zh-CN").format(bytes) + " B";
    if (bytes < 1048576) return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 }).format(bytes / 1024) + " KB";
    if (bytes < 1073741824) return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 }).format(bytes / 1048576) + " MB";
    return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 }).format(bytes / 1073741824) + " GB";
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
      return delay(200).then(function () {
        return { code: 0, message: "ok", data: { datasets: datasets, total: datasets.length } };
      });
    },

    getDatasetImages: function (datasetId, page, pageSize) {
      return delay(200).then(function () {
        var list = getImagesForDataset(datasetId);
        var start = ((page || 1) - 1) * (pageSize || 20);
        var end = start + (pageSize || 20);
        return {
          code: 0,
          message: "ok",
          data: {
            images: list.slice(start, end),
            total: list.length,
            page: page || 1,
            page_size: pageSize || 20,
          },
        };
      });
    },

    createDataset: function (name) {
      return delay(500).then(function () {
        var ds = {
          id: "ds-" + String(datasets.length + 1).padStart(3, "0"),
          name: name,
          image_count: 0,
          annotated_count: 0,
          classes: [],
          total_size: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        datasets.push(ds);
        return { code: 0, message: "ok", data: ds };
      });
    },

    deleteDataset: function (datasetId) {
      return delay(300).then(function () {
        datasets = datasets.filter(function (d) {
          return d.id !== datasetId;
        });
        delete imagesCache[datasetId];
        return { code: 0, message: "ok", data: null };
      });
    },

    getTrainingTasks: function () {
      return delay(200).then(function () {
        return { code: 0, message: "ok", data: { tasks: trainingTasks, total: trainingTasks.length } };
      });
    },

    createTraining: function (config) {
      return delay(500).then(function () {
        var ds = datasets.find(function (d) {
          return d.id === config.dataset_id;
        });
        var versionNum = trainingTasks
          .filter(function (t) {
            return t.dataset_id === config.dataset_id;
          })
          .length + 1;
        var task = {
          id: "task-" + String(trainingTasks.length + 1).padStart(3, "0"),
          dataset_name: ds ? ds.name : "未知",
          dataset_id: config.dataset_id,
          version: "v" + String(versionNum).padStart(3, "0"),
          model_size: config.model_size || "n",
          input_size: config.input_size || 640,
          epochs: config.epochs || 100,
          current_epoch: 0,
          batch_size: config.batch_size || 16,
          learning_rate: config.learning_rate || 0.01,
          device: config.device || "cuda:0",
          status: "running",
          map50: 0,
          map50_95: 0,
          box_loss: 0,
          cls_loss: 0,
          created_at: new Date().toISOString(),
          started_at: new Date().toISOString(),
        };
        trainingTasks.unshift(task);
        return { code: 0, message: "ok", data: task };
      });
    },

    stopTraining: function (taskId) {
      return delay(300).then(function () {
        var task = trainingTasks.find(function (t) {
          return t.id === taskId;
        });
        if (task) {
          task.status = "stopped";
        }
        return { code: 0, message: "ok", data: null };
      });
    },

    getTrainingLog: function (taskId) {
      return delay(100).then(function () {
        var lines = [];
        for (var i = 10; i >= 1; i--) {
          lines.push(
            "[" +
              formatDate(new Date(Date.now() - i * 60000).toISOString()) +
              "] Epoch " +
              (45 - i) +
              "/100  box_loss: " +
              (0.23 + Math.random() * 0.05).toFixed(3) +
              "  cls_loss: " +
              (0.15 + Math.random() * 0.03).toFixed(3) +
              "  mAP@50: " +
              (0.90 + Math.random() * 0.04).toFixed(4)
          );
        }
        return { code: 0, message: "ok", data: { log: lines.join("\n") } };
      });
    },

    getLossCurve: function (taskId) {
      return delay(200).then(function () {
        var epochs = [];
        var boxLoss = [];
        var clsLoss = [];
        var map50 = [];
        for (var i = 1; i <= 45; i++) {
          epochs.push(i);
          boxLoss.push(+(0.5 - i * 0.006 + Math.random() * 0.02).toFixed(3));
          clsLoss.push(+(0.4 - i * 0.005 + Math.random() * 0.015).toFixed(3));
          map50.push(+(0.6 + i * 0.007 + Math.random() * 0.01).toFixed(4));
        }
        return { code: 0, message: "ok", data: { epochs: epochs, box_loss: boxLoss, cls_loss: clsLoss, map50: map50 } };
      });
    },

    getPackages: function () {
      return delay(200).then(function () {
        return { code: 0, message: "ok", data: { packages: packages, total: packages.length } };
      });
    },

    getPackageDetail: function (packageId) {
      return delay(200).then(function () {
        var pkg = packages.find(function (p) {
          return p.id === packageId;
        });
        return { code: 0, message: "ok", data: pkg || null };
      });
    },

    deletePackage: function (packageId) {
      return delay(300).then(function () {
        packages = packages.filter(function (p) {
          return p.id !== packageId;
        });
        return { code: 0, message: "ok", data: null };
      });
    },

    getSystemStatus: function () {
      return delay(100).then(function () {
        return {
          code: 0,
          message: "ok",
          data: {
            status: "ready",
            statusText: "系统正常",
            gpu_usage: 89,
            gpu_memory_used: 8,
            gpu_memory_total: 24,
            gpu_temp: 65,
            gpu_name: "NVIDIA RTX 4090",
            disk_usage: 67,
            disk_used_gb: 335,
            disk_total_gb: 500,
            running_tasks: trainingTasks.filter(function (t) { return t.status === "running"; }).length,
            python_version: "3.10.12",
            cuda_version: "11.8",
            ultralytics_version: "8.0.200",
          },
        };
      });
    },

    getSystemChecks: function () {
      return delay(300).then(function () {
        return { code: 0, message: "ok", data: { status: "ready", checks: systemChecks, last_check: new Date().toISOString() } };
      });
    },

    fixSystem: function () {
      return delay(1500).then(function () {
        return { code: 0, message: "ok", data: { status: "ready", checks: systemChecks } };
      });
    },
  };
})();
