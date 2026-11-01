import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

FILE = Path(__file__).resolve().parents[1] / "bin/omarchy-browser-router"
loader = importlib.machinery.SourceFileLoader("router", str(FILE))
spec = importlib.util.spec_from_loader(loader.name, loader)
r = importlib.util.module_from_spec(spec)
loader.exec_module(r)


class Matching(unittest.TestCase):
    def test_domain_boundary_and_case(self):
        self.assertTrue(r.matches("EXAMPLE.com", "https://example.com/a?q=x"))
        for url in ["https://notexample.com/", "https://example.com.evil.test/", "https://sub.example.com/"]:
            self.assertFalse(r.matches("example.com", url))

    def test_subdomains(self):
        self.assertTrue(r.matches("*.example.com", "https://a.b.example.com/x"))
        self.assertFalse(r.matches("*.example.com", "https://example.com/"))
        self.assertFalse(r.matches("*.example.com", "https://evilexample.com/"))

    def test_path_boundary(self):
        self.assertTrue(r.matches("github.com/team", "https://github.com/team/repo"))
        self.assertTrue(r.matches("github.com/team", "https://github.com/team?x=1"))
        self.assertFalse(r.matches("github.com/team", "https://github.com/teammate"))
        self.assertFalse(r.matches("github.com/Team", "https://github.com/team"))

    def test_scheme_port_and_idna(self):
        self.assertFalse(r.matches("https://example.com", "http://example.com"))
        self.assertTrue(r.matches("localhost:3000/app", "http://localhost:3000/app/foo"))
        self.assertFalse(r.matches("localhost:3000", "http://localhost:4000"))
        self.assertTrue(r.matches("żółw.pl", "https://xn--w-uga1v8h.pl/"))

    def test_reject_unsafe_urls_and_rules(self):
        for url in ["javascript:alert(1)", "file:///etc/passwd", "--incognito", "https://u:p@example.com", "https://example.com/\n", "https://example.com:bad"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                r.validate_url(url)
        for pattern in ["", "example.com?x=1", "example.com/*", "ex*ample.com", "https://user@example.com"]:
            with self.subTest(pattern=pattern), self.assertRaises(ValueError):
                r.pattern_parts(pattern)

    def test_precedence_pause_and_fallback(self):
        config = {"rules": [{"pattern": "example.com/team", "target": "ask"}, {"pattern": "example.com", "target": "work"}], "fallback": "personal"}
        self.assertEqual(r.resolve(config, "https://example.com/team")[0], "ask")
        self.assertEqual(r.resolve(config, "https://example.com/other")[0], "work")
        self.assertEqual(r.resolve(config, "https://unmatched.test")[0], "personal")
        config["paused"] = True
        self.assertEqual(r.resolve(config, "https://example.com/team")[0], "personal")


class Isolated(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(r, "HOME", self.root), patch.object(r, "CONFIG_HOME", self.root / "config"), patch.object(r, "CONFIG", self.root / "config/omarchy/browser-router.json"), patch.object(r, "STATE", self.root / "state"), patch.object(r, "DATA_HOME", self.root / "data")]
        for p in self.patches:
            p.start()
        self.addCleanup(self.temp.cleanup)
        for p in self.patches:
            self.addCleanup(p.stop)

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)

    def target(self, family="chromium"):
        return {"id": "brave.desktop::work", "desktop": "brave.desktop", "family": family, "argv": ["brave"], "profile": "Profile 1" if family == "chromium" else "/profiles/work", "root": "/browser/data", "label": "Work"}

    def test_discovery_native_chromium_and_firefox(self):
        for binary, desktop in [("brave", "brave-browser"), ("firefox", "firefox")]:
            self.put(r.DATA_HOME / f"applications/{desktop}.desktop", f"[Desktop Entry]\nName={binary}\nExec={binary} %U\nMimeType=x-scheme-handler/https;\n")
        brave_root = r.CONFIG_HOME / "BraveSoftware/Brave-Browser"
        (brave_root / "Profile 1").mkdir(parents=True)
        self.put(brave_root / "Local State", json.dumps({"profile": {"info_cache": {"Profile 1": {"name": "<img src='https://evil.test'>"}, "../../evil": {"name": "Bad"}}}}))
        firefox_root = r.HOME / ".mozilla/firefox"
        (firefox_root / "abc.work").mkdir(parents=True)
        self.put(firefox_root / "profiles.ini", "[Profile0]\nName=Work\nPath=abc.work\nIsRelative=1\n")
        with patch.object(r, "data_dirs", return_value=[r.DATA_HOME]), patch.object(r.shutil, "which", side_effect=lambda x: "/usr/bin/" + x if x in ("brave", "firefox") else None):
            targets = r.discover()
        profiles = [t for t in targets if t["profile"]]
        self.assertEqual(len(profiles), 2)
        firefox = next(t for t in profiles if t["family"] == "firefox")
        self.assertEqual(firefox["profile"], str(firefox_root / "abc.work"))
        self.assertFalse(any(t["profile"] == "../../evil" for t in profiles))

    def test_flatpak_discovery(self):
        self.put(r.DATA_HOME / "applications/com.brave.Browser.desktop", "[Desktop Entry]\nName=Brave (Flatpak)\nExec=/usr/bin/flatpak run --branch=stable com.brave.Browser %U\nMimeType=x-scheme-handler/https;\n")
        root = r.HOME / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser"
        (root / "Default").mkdir(parents=True)
        self.put(root / "Local State", json.dumps({"profile": {"info_cache": {"Default": {"name": "Personal"}}}}))
        with patch.object(r, "data_dirs", return_value=[r.DATA_HOME]), patch.object(r.shutil, "which", side_effect=lambda x: x if x == "/usr/bin/flatpak" else None):
            profiles = [t for t in r.discover() if t["profile"]]
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["root"], str(root))

    def test_argument_safety_and_selected_profile(self):
        url = "https://example.com/$(touch%20/tmp/oops)?q=`id`&x=1"
        with patch.object(r.subprocess, "Popen") as popen:
            command = r.launch(self.target(), [url])
        self.assertEqual(command[-1], url)
        self.assertIn("--profile-directory=Profile 1", command)
        self.assertIn("--user-data-dir=/browser/data", command)
        self.assertNotIn("shell", popen.call_args.kwargs)
        with patch.object(r.subprocess, "Popen"):
            command = r.launch(self.target("firefox"), [url], private=True)
        self.assertIn("/profiles/work", command)
        self.assertIn("-private-window", command)

    def test_router_never_recurses_on_itself(self):
        config = {"previous_browser": "brave.desktop"}
        target = {**self.target(), "id": "brave.desktop"}
        with patch.object(r, "system_browser", return_value=r.DESKTOP):
            self.assertEqual(r.system_target(config, [target]), target)
            with self.assertRaises(ValueError):
                r.system_target({}, [target])

    def test_enable_and_restore_distinct_handlers(self):
        config = {"version": 1, "rules": []}
        with patch.object(r, "system_browser", return_value="brave.desktop"), patch.object(r, "run", side_effect=[Mock(stdout="brave.desktop\n"), Mock(stdout="firefox.desktop\n")]), patch.object(r, "set_handler") as setter:
            r.activate(config)
        self.assertEqual(config["previous_browser"], "brave.desktop")
        self.assertEqual(len(setter.call_args_list), 2)
        with patch.object(r, "run", return_value=Mock(stdout=r.DESKTOP)), patch.object(r, "set_handler") as setter:
            r.deactivate(config)
        self.assertEqual(setter.call_args_list[0].args, ("brave.desktop", "x-scheme-handler/http"))
        self.assertEqual(setter.call_args_list[1].args, ("firefox.desktop", "x-scheme-handler/https"))

    def test_pending_private_permissions_and_cancel(self):
        r.enqueue("https://example.com", True)
        request = r.pending()[0]
        path = r.request_path(request["id"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertTrue(request["private"])
        with patch.object(r, "discover", return_value=[]), patch.object(r, "snapshot", return_value={}):
            r.action("cancel", {"id": request["id"]})
        self.assertFalse(path.exists())
        with self.assertRaises(ValueError):
            r.request_path("../escape")

    def test_failed_activation_rolls_back_first_handler(self):
        config = {"version": 1, "rules": []}
        with patch.object(r, "system_browser", return_value="brave.desktop"), patch.object(r, "run", return_value=Mock(stdout="brave.desktop\n")), patch.object(r, "set_handler", side_effect=[None, ValueError("failed"), None]) as setter:
            with self.assertRaises(ValueError):
                r.activate(config)
        self.assertEqual(setter.call_args_list[-1].args, ("brave.desktop", "x-scheme-handler/http"))
        self.assertEqual(r.read_json(r.CONFIG)["previous_browser"], "brave.desktop")

    def test_disable_preserves_newly_selected_browser(self):
        config = {"previous_browser": "old.desktop"}
        with patch.object(r, "run", side_effect=[Mock(stdout="new.desktop"), Mock(stdout=r.DESKTOP)]), patch.object(r, "set_handler") as setter:
            r.deactivate(config)
        setter.assert_called_once_with("old.desktop", "x-scheme-handler/https")

    def test_flatpak_file_forwarding_markers_are_removed(self):
        entry = {"exec": "/usr/bin/flatpak run --file-forwarding com.brave.Browser @@u %U @@"}
        with patch.object(r.shutil, "which", return_value="/usr/bin/flatpak"):
            self.assertEqual(r.exec_argv(entry), ["/usr/bin/flatpak", "run", "com.brave.Browser"])

    def test_unavailable_shell_preserves_queued_url(self):
        r.write_json(r.CONFIG, {"version": 1, "rules": [], "fallback": "ask"})
        with patch.object(r, "discover", return_value=[]), patch.object(r, "run", return_value=Mock(returncode=0, stdout="unknown")):
            with self.assertRaises(ValueError):
                r.route(["https://example.com"])
        self.assertEqual(r.pending()[0]["url"], "https://example.com")

    def test_missing_profile_asks_and_dry_run_does_not_enqueue(self):
        config = {"version": 1, "rules": [], "fallback": "missing"}
        r.write_json(r.CONFIG, config)
        with patch.object(r, "discover", return_value=[]), patch.object(r, "summon") as summon:
            decisions = r.route(["https://example.com"], dry_run=True)
            self.assertEqual(decisions[0]["target"], "ask")
            self.assertEqual(r.pending(), [])
            r.route(["https://example.com"])
            self.assertEqual(len(r.pending()), 1)
            summon.assert_called_once()

    def test_always_adds_first_and_opens_only_selected_profile(self):
        r.write_json(r.CONFIG, {"version": 1, "rules": [{"id": "existing", "pattern": "example.com", "target": "ask"}], "fallback": "system"})
        r.enqueue("https://example.com/path")
        request = r.pending()[0]
        with patch.object(r, "discover", return_value=[self.target()]), patch.object(r, "launch") as launch, patch.object(r, "snapshot", return_value={}):
            r.action("choose", {"id": request["id"], "target": self.target()["id"], "remember": True})
            launch.assert_called_once_with(self.target(), ["https://example.com/path"], False)
        self.assertEqual(r.load_config()["rules"][0]["target"], self.target()["id"])
        self.assertEqual(r.pending(), [])

    def test_host_ui_sinks_escape_markup(self):
        qml = (FILE.parents[1] / "Settings.qml").read_text()
        self.assertIn('root.safe(t.label)', qml)
        self.assertIn('replace(/</g, "&lt;")', qml)
        plain = (FILE.parents[1] / "PlainText.qml").read_text()
        self.assertIn('textFormat: Text.PlainText', plain)


if __name__ == "__main__":
    unittest.main()
