from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH)
datas, binaries, hiddenimports = [], [], []


def runtime_submodule(name):
    if name.startswith("onnxruntime"):
        # InferenceSession and native pybind only. Training, model conversion,
        # quantization and transformer authoring tools are build/developer APIs.
        return name == "onnxruntime" or (name.startswith("onnxruntime.capi")
                                         and not name.endswith(".convert_npz_to_onnx"))
    return name not in {"gigaam.onnx_utils", "gigaam.vad_utils"} and not name.startswith("hydra.test_utils")


for package in ("gigaam", "hydra", "omegaconf", "sentencepiece", "pyaudiowpatch", "docx", "reportlab", "onnxruntime"):
    d, b, h = collect_all(package, include_py_files=True, on_error="warn once",
                          filter_submodules=runtime_submodule)
    d = [entry for entry in d if "hydra/test_utils/" not in str(entry[0]).replace("\\", "/")
         and not str(entry[0]).replace("\\", "/").endswith(("gigaam/onnx_utils.py", "gigaam/vad_utils.py"))]
    if package == "onnxruntime":
        unused = ("/onnxruntime/tools/", "/onnxruntime/transformers/", "/onnxruntime/quantization/",
                  "/onnxruntime/backend/", "/onnxruntime/datasets/", "/onnxruntime/experimental/")
        d = [entry for entry in d if not any(part in str(entry[0]).replace("\\", "/") for part in unused)]
    datas += d
    binaries += b
    hiddenimports += h
for package in ("torch", "torchaudio", "onnxruntime"):
    binaries += collect_dynamic_libs(package)
for distribution in ("gigaam", "torch", "torchaudio", "PyAudioWPatch", "python-docx", "reportlab", "onnxruntime"):
    datas += copy_metadata(distribution)
for name in ("vcruntime140.dll", "vcruntime140_1.dll"):
    path = Path(sys.base_prefix) / name
    if path.is_file():
        binaries.append((str(path), "."))
a = Analysis([str(root / "app.py")], pathex=[str(root)], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports + ["_cffi_backend", "tkinter", "tkinter.ttk", "tkinter.filedialog",
        "tkinter.messagebox", "gigaam.encoder", "gigaam.decoder", "gigaam.decoding", "gigaam.preprocess",
        "onnxruntime.capi._pybind_state", "onnxruntime.capi.onnxruntime_pybind11_state"],
    excludes=["pytest", "IPython", "matplotlib", "pandas", "scipy", "numba", "pyannote", "transformers",
              "torchcodec", "gigaam.vad_utils", "gigaam.onnx_utils", "onnx", "ml_dtypes",
              "onnxruntime.tools", "onnxruntime.transformers", "onnxruntime.quantization", "onnxruntime.backend",
              "onnxruntime.datasets", "onnxruntime.experimental", "onnxruntime.training",
              "sounddevice", "soundfile", "_soundfile", "_soundfile_data"],
    noarchive=False)
# Hydra's standard PyInstaller hook adds its development fixtures again after
# our explicit collection. They are unused and can exceed Windows MAX_PATH.
a.datas = [entry for entry in a.datas if "hydra/test_utils/" not in str(entry[0]).replace("\\", "/")
           and not str(entry[0]).replace("\\", "/").endswith(("gigaam/onnx_utils.py", "gigaam/vad_utils.py"))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="GigaAM-Speakers", debug=False,
          strip=False, upx=False, console=False, disable_windowed_traceback=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="GigaAM-Speakers")
