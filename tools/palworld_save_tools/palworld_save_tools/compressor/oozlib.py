import importlib
import importlib.util
import platform
import sys
from pathlib import Path

from palworld_save_tools.compressor import (
    Compressor,
    SaveType
)

class OodleCompressor:
    Kraken    = 8
    Mermaid   = 9
    Selkie    = 11
    Hydra     = 12  # hydra doesn't exist in libooz
    Leviathan = 13

class OodleLevel:
    SuperFast = 1
    VeryFast  = 2
    Fast      = 3
    Normal    = 4
    Optimal1  = 5
    Optimal2  = 6
    Optimal3  = 7
    Optimal4  = 8
    Optimal5  = 9

    HyperFast1 = -1
    HyperFast2 = -2
    HyperFast3 = -3
    HyperFast4 = -4


class OozLib(Compressor):
    def __init__(self):
        """
        OozLib is an open source library for compression and decompression using Oodle.
        """
        self.SAFE_SPACE_PADDING = 128
        self.__load_ooz()
        
    def __load_ooz(self):
        """
        Load the Ooz library dynamically based on the platform.
        This is done to ensure compatibility with different operating systems.
        """
        lib_path = ''

        if sys.platform == 'win32':
            lib_path = 'windows'
        elif sys.platform == 'linux':
            arch = platform.machine().lower()
            if 'aarch64' in arch or 'arm' in arch:
                lib_path = 'linux_arm64'
            elif 'x86_64' in arch or 'amd64' in arch:
                lib_path = 'linux_x86_64'
            else:
                raise Exception(f"Unsupported Linux architecture: {arch}")
        elif sys.platform == 'darwin':
            arch = platform.machine().lower()
            if 'arm64' in arch:
                lib_path = 'mac_arm64'
            elif 'x86_64' in arch:
                lib_path = 'mac_x86_64'
            else:
                raise Exception(f"Unsupported Mac architecture: {arch}")
        else:
            raise Exception(f"Unsupported platform: {sys.platform}")
        
        search_dirs = self.__collect_ooz_search_dirs(lib_path)
        import_errors = []

        for candidate_dir in search_dirs:
            if not candidate_dir.is_dir():
                continue

            candidate_dir_str = str(candidate_dir)
            if candidate_dir_str not in sys.path:
                sys.path.insert(0, candidate_dir_str)

            try:
                self.ooz = importlib.import_module("ooz")
                return
            except ImportError as exc:
                import_errors.append(f"{candidate_dir}: {exc}")

            loaded_module = self.__load_ooz_from_files(candidate_dir)
            if loaded_module is not None:
                self.ooz = loaded_module
                return

        searched_locations = ", ".join(str(path) for path in search_dirs)
        detail = " | ".join(import_errors) if import_errors else "no import attempts succeeded"
        raise ImportError(
            "Failed to import 'ooz' module. "
            f"Searched locations: {searched_locations}. "
            f"Details: {detail}. "
            "Make sure the bundled Ooz library exists or install latest pyooz using "
            "'pip install git+https://github.com/MRHRTZ/pyooz.git'"
        )

    def __collect_ooz_search_dirs(self, lib_path: str):
        module_dir = Path(__file__).resolve().parent
        search_dirs = []

        def add_candidate(path: Path):
            normalized = path.resolve()
            if normalized not in search_dirs:
                search_dirs.append(normalized)

        add_candidate(module_dir.parent / "lib" / lib_path)

        if hasattr(sys, "_MEIPASS"):
            meipass_dir = Path(sys._MEIPASS).resolve()
            add_candidate(meipass_dir)
            add_candidate(meipass_dir / "palworld_save_tools" / "palworld_save_tools" / "lib" / lib_path)
            add_candidate(meipass_dir / "palworld_save_tools" / "lib" / lib_path)
            add_candidate(meipass_dir / "lib" / lib_path)

        if getattr(sys, "frozen", False):
            executable_dir = Path(sys.executable).resolve().parent
            add_candidate(executable_dir)
            add_candidate(executable_dir / "palworld_save_tools" / "palworld_save_tools" / "lib" / lib_path)
            add_candidate(executable_dir / "palworld_save_tools" / "lib" / lib_path)
            add_candidate(executable_dir / "lib" / lib_path)
            for parent_dir in executable_dir.parents:
                add_candidate(parent_dir / "tools" / "palworld_save_tools" / "palworld_save_tools" / "lib" / lib_path)

        return search_dirs

    def __load_ooz_from_files(self, directory: Path):
        suffixes = [".pyd", ".so", ".dylib"]
        for suffix in suffixes:
            for library_file in directory.glob(f"ooz*{suffix}"):
                try:
                    spec = importlib.util.spec_from_file_location("ooz", library_file)
                    if spec is None or spec.loader is None:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    sys.modules["ooz"] = module
                    spec.loader.exec_module(module)
                    return module
                except Exception:
                    sys.modules.pop("ooz", None)
        return None
        
    def compress(self, data: bytes, save_type: int) -> bytes:
        uncompressed_len = len(data)
        if uncompressed_len == 0:
            raise ValueError("Input data for compression must not be empty.")

        if save_type != SaveType.PLM:
            raise ValueError(
                f"Unhandled compression type: 0x{save_type:02X}, only 0x31 (PLM) is supported"
            )

        compressed_data = self.ooz.compress(
            OodleCompressor.Kraken, 
            OodleLevel.Normal,
            data,
            uncompressed_len
        )

        if not compressed_data:
            raise RuntimeError(f"Ooz_Compress failed or returned empty result (code: {compressed_data})")

        compressed_len = len(compressed_data)
        magic_bytes = self._get_magic(save_type)
        
        sav_data = self.build_sav(
            compressed_data,
            uncompressed_len,
            compressed_len,
            magic_bytes,
            save_type
        )
        
        return sav_data

    def decompress(self, data: bytes) -> bytes:
        if not data:
            raise ValueError("SAV data cannot be empty")

        format_result = self.check_sav_format(data)
        if format_result == 0:
            raise ValueError(
                "Detected PLZ format (Zlib), this tool only supports PLM format (Oodle)"
            )
        elif format_result == -1:
            raise ValueError("Unknown SAV file format")

        
        uncompressed_len, compressed_len, magic, save_type, data_offset = (
            self._parse_sav_header(data)
        )
    
        compressed_data = data[data_offset : data_offset + compressed_len]
        decompressed = self.ooz.decompress(compressed_data, uncompressed_len)
        
        if len(decompressed) != uncompressed_len:
            raise ValueError(
                f"Decompressed data length {len(decompressed)} does not match expected uncompressed length {uncompressed_len}"
            )
        
        return decompressed, save_type

    
    
        
