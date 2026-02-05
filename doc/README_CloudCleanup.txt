Cloud Cleanup Tool - Quick Start Guide
======================================

OVERVIEW
--------
This tool cleans training models, datasets and temporary files from cloud server
to avoid conflicts with future training tasks.

FILES
-----
- cloud_cleanup.py          : Main cleanup script
- cloud_config.json         : Configuration file  
- run_cloud_cleanup.bat     : Windows batch launcher
- test_cloud_connection.py  : Connection test script
- README_CloudCleanup.txt   : This guide

QUICK START
-----------
1. Double-click "run_cloud_cleanup.bat"
2. Review the files to be deleted
3. Type "YES" to confirm cleanup

WHAT WILL BE CLEANED
--------------------
- /root/yolo_dataset/        : Training dataset (355MB)
- /root/runs/train/          : Training results  
- /root/runs/detect/         : Detection results
- /root/runs/val/            : Validation results
- Model files (*.pt, *.pth, *.onnx)
- Image files (*.jpg, *.png)
- Log files and temporary data

SAFETY FEATURES
---------------
- Preview before deletion
- Confirmation required (type "YES")
- Protected system directories
- Detailed operation logs
- Cleanup report generation

CURRENT STATUS
--------------
✓ Server connection: 152.136.245.138 (READY)
✓ Configuration: Valid
✓ Target directories found: ~2.3GB to clean

TROUBLESHOOTING
---------------
- Connection failed: Check server IP/password
- Permission denied: Ensure root access
- Network timeout: Check internet connection

For detailed logs, check the generated .log files.