import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", SOURCE / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class Installer(unittest.TestCase):
    def test_missing_hostname_dependency_stops_before_install(self):
        with patch.object(installer.shutil, "which", return_value="/mock/omarchy"), patch.object(installer.importlib.util, "find_spec", return_value=None), patch.object(installer.shutil, "copytree") as copy, patch.object(installer.subprocess, "run") as run, patch("sys.argv", ["install.py"]):
            with self.assertRaisesRegex(SystemExit, "omarchy pkg add python-idna"):
                installer.main()
        copy.assert_not_called()
        run.assert_not_called()

    def test_install_and_uninstall_preserve_unrelated_shell_settings(self):
        with tempfile.TemporaryDirectory(prefix="router space ") as folder:
            root = Path(folder)
            config_home = root / "config"
            data_home = root / "data"
            destination = config_home / "omarchy/plugins" / installer.PLUGIN
            bindir = root / ".local/bin"
            path = config_home / "omarchy/shell.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"idle": {"lock": 99}, "plugins": [{"id": "other.plugin"}]}))
            with patch.multiple(installer, HOME=root, CONFIG_HOME=config_home, DATA_HOME=data_home, DEST=destination, BINDIR=bindir), patch.object(installer.subprocess, "run") as run, patch.object(installer.shutil, "which", return_value="/mock/omarchy"):
                with patch("sys.argv", ["install.py", "--enable-plugin"]):
                    installer.main()
                config = json.loads(path.read_text())
                self.assertEqual(config["idle"]["lock"], 99)
                self.assertIn({"id": installer.PLUGIN}, config["plugins"])
                self.assertTrue(list(path.parent.glob("shell.json.browser-router-backup-*")))
                desktop = (data_home / "applications/omarchy-browser-router.desktop").read_text()
                self.assertIn('Exec=omarchy-browser-router open %U', desktop)
                self.assertFalse(any("xdg-mime" in str(call) for call in run.call_args_list))
                self.assertTrue((destination / "bin/omarchy-browser-router").stat().st_mode & 0o111)
                installer.update_shell(True, bar_icon=True)
                config = json.loads(path.read_text())
                self.assertIn({"id": installer.PLUGIN}, config["bar"]["layout"]["right"])
                self.assertNotIn({"id": installer.PLUGIN}, config["plugins"])
                installer.update_shell(True)
                config = json.loads(path.read_text())
                self.assertNotIn({"id": installer.PLUGIN}, config["plugins"])
                with patch("sys.argv", ["install.py", "--uninstall"]):
                    installer.main()
                config = json.loads(path.read_text())
                self.assertEqual(config["plugins"], [{"id": "other.plugin"}])
                self.assertEqual(config["idle"]["lock"], 99)
                self.assertFalse((bindir / "omarchy-browser-router").exists())
                self.assertFalse(destination.exists())

    def test_browser_exec_avoids_quotes_for_omarchy(self):
        self.assertEqual(installer.browser_exec(Path("/home/user/.local/bin/omarchy-browser-router")), "/home/user/.local/bin/omarchy-browser-router")
        for folder in ("home with spaces", 'home"quote', "home$dollar"):
            self.assertEqual(installer.browser_exec(Path("/home") / folder / "omarchy-browser-router"), "omarchy-browser-router")

    @unittest.skipUnless(shutil.which("omarchy-cmd-default-browser"), "Requires installed Omarchy launcher")
    def test_real_omarchy_resolver_recognizes_router(self):
        resolver = shutil.which("omarchy-cmd-default-browser")
        for prefix in ("router-normal-", "router space "):
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory(prefix=prefix) as folder:
                root = Path(folder)
                config_home = root / "config"
                data_home = root / "data"
                bindir = root / ".local/bin"
                destination = config_home / "omarchy/plugins" / installer.PLUGIN
                with patch.multiple(installer, HOME=root, CONFIG_HOME=config_home, DATA_HOME=data_home, DEST=destination, BINDIR=bindir), patch.object(installer.subprocess, "run"), patch.object(installer.shutil, "which", return_value="/mock/omarchy"), patch("sys.argv", ["install.py"]):
                    installer.main()
                (config_home / "mimeapps.list").write_text("[Default Applications]\nx-scheme-handler/http=omarchy-browser-router.desktop\nx-scheme-handler/https=omarchy-browser-router.desktop\n")
                (config_home / "hyprland-mimeapps.list").write_text("[Default Applications]\nx-scheme-handler/http=omarchy-browser.desktop\n")
                env = {**os.environ, "XDG_CONFIG_HOME": str(config_home), "XDG_CONFIG_DIRS": str(root / "empty"), "XDG_DATA_HOME": str(data_home), "XDG_DATA_DIRS": str(root / "empty"), "XDG_CURRENT_DESKTOP": "Hyprland", "PATH": str(bindir) + os.pathsep + os.environ["PATH"]}
                env.pop("BROWSER", None)
                result = subprocess.run([resolver], env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "omarchy-browser-router.desktop")


if __name__ == "__main__":
    unittest.main()
