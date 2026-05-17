import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.domain.saju.services import solar_term_boundaries
from app.tools import ensure_skyfield_ephemeris as ensure


class SkyfieldEphemerisToolTests(unittest.TestCase):
    def test_check_ephemeris_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ensure.SKYFIELD_EPHEMERIS

            with self.assertRaises(FileNotFoundError):
                ensure.check_ephemeris(path)

    def test_check_ephemeris_validates_size_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ensure.SKYFIELD_EPHEMERIS
            path.write_bytes(b"abc")

            with patch.object(ensure, "SKYFIELD_EPHEMERIS_SIZE_BYTES", 3), patch.object(
                ensure,
                "SKYFIELD_EPHEMERIS_SHA256",
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            ):
                status = ensure.check_ephemeris(path)

        self.assertTrue(status["exists"])
        self.assertTrue(status["size_matches"])
        self.assertTrue(status["sha256_matches"])

    def test_runtime_loader_does_not_download_missing_ephemeris(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                "os.environ",
                {solar_term_boundaries.SKYFIELD_CACHE_ENV: temp_dir},
            ):
                solar_term_boundaries._skyfield_runtime.cache_clear()
                with self.assertRaises(FileNotFoundError):
                    solar_term_boundaries._skyfield_runtime()
                self.assertFalse((Path(temp_dir) / ensure.SKYFIELD_EPHEMERIS).exists())
                solar_term_boundaries._skyfield_runtime.cache_clear()


if __name__ == "__main__":
    unittest.main()
