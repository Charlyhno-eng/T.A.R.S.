from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.linux_install import clean_linux_exports, desktop_entry, install_bundle, linux_exports


def make_bundle(path: Path, content: bytes = b"application") -> Path:
    icon = path / "_internal" / "assets" / "tars-mascot.png"
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"icon")
    executable = path / "TARS"
    executable.write_bytes(content)
    executable.chmod(0o755)
    return path


class LinuxInstallTests(unittest.TestCase):
    def test_install_moves_bundle_and_creates_menu_entry_outside_checkout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tars space ") as temporary:
            root = Path(temporary)
            bundle = make_bundle(root / "dist" / "TARS")
            installation = root / ".local" / "lib" / "tars"
            launcher = install_bundle(bundle, installation, root / "applications")
            self.assertFalse(bundle.exists())
            self.assertEqual((installation / "TARS").read_bytes(), b"application")
            self.assertTrue((installation / "_internal" / "assets" / "tars-mascot.png").is_file())
            self.assertIn(f'Exec="{installation}/TARS"', launcher.read_text())
            self.assertIn("Terminal=false", launcher.read_text())

    def test_failed_launcher_update_restores_previous_install_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle(root / "new")
            installation = make_bundle(root / "installed", b"previous")
            applications = root / "applications"
            applications.mkdir()
            launcher = applications / "tars.desktop"
            launcher.write_text("previous launcher")
            with patch("core.linux_install.Path.replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    install_bundle(bundle, installation, applications)
            self.assertEqual((bundle / "TARS").read_bytes(), b"application")
            self.assertEqual((installation / "TARS").read_bytes(), b"previous")
            self.assertEqual(launcher.read_text(), "previous launcher")

    def test_new_install_replaces_previous_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = make_bundle(root / "new", b"updated")
            installation = make_bundle(root / "installed", b"previous")
            launcher = install_bundle(bundle, installation, root / "applications")
            self.assertEqual((installation / "TARS").read_bytes(), b"updated")
            self.assertTrue(launcher.is_file())
            self.assertFalse(bundle.exists())
            self.assertFalse(list(root.glob(".tars-install-*")))

    def test_cleanup_preserves_unrelated_files_and_other_platforms(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dist = Path(temporary)
            old = dist / "TARS-linux-x86_64-20260930-235228-222579"
            newest = dist / "TARS-linux-x86_64-20261001-000908-286552"
            make_bundle(old / "TARS")
            newest.mkdir()
            windows = dist / "TARS-windows-x86_64-20260930-235228-222579"
            windows.mkdir()
            unrelated = dist / "notes.txt"
            unrelated.write_text("keep")
            protected = dist / "TARS-linux-x86_64-20260929-235228-222579"
            make_bundle(protected / "TARS")
            (protected / "notes.txt").write_text("keep")
            self.assertEqual(linux_exports(dist)[-1], newest)
            clean_linux_exports(dist)
            self.assertFalse(old.exists())
            self.assertFalse(newest.exists())
            self.assertTrue(windows.exists() and unrelated.exists() and protected.exists())

    def test_rejects_incomplete_bundle_before_replacing_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = make_bundle(root / "installed", b"previous")
            with self.assertRaises(ValueError):
                install_bundle(root / "missing", installation, root / "applications")
            self.assertEqual((installation / "TARS").read_bytes(), b"previous")

    def test_exec_escapes_desktop_field_codes_and_reserved_characters(self) -> None:
        entry = desktop_entry(Path('/tmp/space % " $ ` \\ /tars'))
        self.assertIn('Exec="/tmp/space %% \\\\" \\\\$ \\\\` \\\\\\\\ /tars/TARS"', entry)
        with self.assertRaises(ValueError):
            desktop_entry(Path("/tmp/new\nline"))
