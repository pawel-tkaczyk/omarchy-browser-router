#!/usr/bin/env python3
"""Install the public plugin and its XDG handler without changing browser defaults."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PLUGIN = "paweltkaczyk.browser-router"
SOURCE = Path(__file__).resolve().parent
HOME = Path.home()
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
DEST = CONFIG_HOME / "omarchy/plugins" / PLUGIN
BINDIR = HOME / ".local/bin"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-plugin", action="store_true", help="Enable the panel in shell.json; does not change the default browser")
    parser.add_argument("--bar-icon", action="store_true", help="Enable the plugin with a bar icon instead of a panel-only entry")
    parser.add_argument("--uninstall", action="store_true", help="Restore browser handlers and remove installed plugin (keeps rules)")
    args = parser.parse_args()
    command = BINDIR / "omarchy-browser-router"
    if args.uninstall:
        if command.exists():
            subprocess.run([str(command), "action", "deactivate", "{}"], check=True)
        update_shell(False)
        command.unlink(missing_ok=True)
        (DATA_HOME / "applications/omarchy-browser-router.desktop").unlink(missing_ok=True)
        (DATA_HOME / "applications/omarchy-browser-router-settings.desktop").unlink(missing_ok=True)
        # Never remove the source repository if installing from the plugin directory.
        if DEST.exists() and DEST.resolve() != SOURCE:
            shutil.rmtree(DEST)
        print("Uninstalled. Rules retained in ~/.config/omarchy/browser-router.json")
        return
    if not shutil.which("omarchy"):
        sys.exit("Omarchy is required")
    subprocess.run(["omarchy", "plugin", "validate", str(SOURCE)], check=True)
    if SOURCE != DEST.resolve():
        if DEST.exists():
            installed = json.loads((DEST / "manifest.json").read_text())
            if installed.get("id") != PLUGIN:
                sys.exit("The destination belongs to another plugin")
        shutil.copytree(SOURCE, DEST, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "dist"))
    BINDIR.mkdir(parents=True, exist_ok=True)
    # A small launcher keeps the helper path stable across plugin updates.
    executable = str(DEST / "bin/omarchy-browser-router")
    command.write_text("#!/usr/bin/env python3\nimport os, sys\nos.execv(" + repr(executable) + ", [" + repr(executable) + "] + sys.argv[1:])\n")
    command.chmod(0o755)
    (DEST / "bin/omarchy-browser-router").chmod(0o755)
    applications = DATA_HOME / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    # Desktop entry quoting is distinct from shell quoting.
    path = str(command).replace("\\", "\\\\\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
    (applications / "omarchy-browser-router.desktop").write_text(
        '[Desktop Entry]\nType=Application\nName=Browser Router\nComment=Route links to browser profiles\n'
        f'Exec="{path}" open %U\nIcon=web-browser\nTerminal=false\nNoDisplay=true\n'
        'Categories=Network;WebBrowser;\nMimeType=x-scheme-handler/http;x-scheme-handler/https;\n')
    (applications / "omarchy-browser-router-settings.desktop").write_text(
        '[Desktop Entry]\nType=Application\nName=Browser Router Settings\n'
        f'Exec="{path}" settings\nIcon=web-browser\nTerminal=false\nCategories=Settings;\n')
    if args.enable_plugin or args.bar_icon:
        update_shell(True, args.bar_icon)
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(applications)], check=False)
    print(f"Installed into {DEST}")
    print("Open Browser Router Settings from the launcher, then choose Enable routing.")
    print("Your default browser has not been changed.")


def update_shell(enable, bar_icon=False):
    path = CONFIG_HOME / "omarchy/shell.json"
    config = json.loads(path.read_text()) if path.exists() else {}
    plugins = [entry for entry in config.get("plugins", []) if entry.get("id") != PLUGIN]
    layout = config.get("bar", {}).get("layout", {})
    in_bar = any(e.get("id") == PLUGIN for entries in layout.values() for e in entries)
    if enable:
        if bar_icon and not in_bar:
            config.setdefault("bar", {}).setdefault("layout", {}).setdefault("right", []).append({"id": PLUGIN})
        elif not in_bar and not bar_icon:
            plugins.append({"id": PLUGIN})
        config["disabledPlugins"] = [p for p in config.get("disabledPlugins", []) if p != PLUGIN]
    else:
        for entries in config.get("bar", {}).get("layout", {}).values():
            entries[:] = [e for e in entries if e.get("id") != PLUGIN]
    config["plugins"] = plugins
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name("shell.json.browser-router-backup-" + str(time.time_ns())))
    temporary = path.with_name("shell.json.browser-router-tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n")
    temporary.replace(path)


if __name__ == "__main__":
    main()
