import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", SOURCE / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class Installer(unittest.TestCase):
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
            with patch.multiple(installer, HOME=root, CONFIG_HOME=config_home, DATA_HOME=data_home, DEST=destination, BINDIR=bindir), patch.object(installer.subprocess, "run") as run:
                with patch("sys.argv", ["install.py", "--enable-plugin"]):
                    installer.main()
                config = json.loads(path.read_text())
                self.assertEqual(config["idle"]["lock"], 99)
                self.assertIn({"id": installer.PLUGIN}, config["plugins"])
                self.assertTrue(list(path.parent.glob("shell.json.browser-router-backup-*")))
                desktop = (data_home / "applications/omarchy-browser-router.desktop").read_text()
                self.assertIn('Exec="' + str(bindir / "omarchy-browser-router") + '" open %U', desktop)
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


if __name__ == "__main__":
    unittest.main()
