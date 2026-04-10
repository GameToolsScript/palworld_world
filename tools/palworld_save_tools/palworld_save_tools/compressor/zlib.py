import zlib

from palworld_save_tools.compressor import (
    Compressor,
    SaveType
)

class Zlib(Compressor):
    def __init__(self):
        """
        OozLib is an open source library for compression and decompression using Oodle.
        """
        self.SAFE_SPACE_PADDING = 128
        
    def compress(self, data: bytes, save_type: int) -> bytes:
        uncompressed_len = len(data)
        compressed_data = zlib.compress(data)
        compressed_len = len(compressed_data)
        if save_type != 0x32:
            raise Exception(
                f"Unhandled compression type: 0x{save_type:02X}, only 0x32 (double zlib) is supported"
            )
        compressed_data = zlib.compress(compressed_data)
        magic_bytes = self._get_magic(save_type)

        sav_data = self.build_sav(        
            compressed_data,
            uncompressed_len,
            compressed_len,
            magic_bytes,
            save_type,
        )

        return sav_data

    def decompress(self, data: bytes) -> bytes:
        format_result = self.check_sav_format(data)
        if format_result == 1:
            raise ValueError(
                "Detected PLM format (Oodle), this tool only supports PLZ format (Zlib)"
            )
        elif format_result == -1:
            raise ValueError("Unknown SAV file format")

        
        uncompressed_len, compressed_len, magic, save_type, data_offset = (
            self._parse_sav_header(data)
        )
        
        uncompressed_data = zlib.decompress(data[data_offset:])
        
        if save_type == SaveType.PLZ:
            if compressed_len != len(uncompressed_data):
                raise Exception(f"incorrect compressed length: {compressed_len}")
            
            uncompressed_data = zlib.decompress(uncompressed_data)
            
        if uncompressed_len != len(uncompressed_data):
            raise Exception(f"incorrect uncompressed length: {uncompressed_len}")

        return uncompressed_data, save_type
