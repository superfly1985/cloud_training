param(
  [switch]$GPU
)
Write-Host "[setup] 初始化虚拟环境与依赖..."
$ErrorActionPreference = 'Stop'
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
if ($GPU) {
  Write-Host "[setup] 安装 CUDA 版 PyTorch（请确认 CUDA 版本）"
  python -m pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
} else {
  Write-Host "[setup] 安装 CPU 版依赖"
  python -m pip install -r requirements.txt
}
Write-Host "[setup] 完成。"
