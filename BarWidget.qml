import QtQuick
import Quickshell
import qs.Ui
import qs.Commons

BarWidget {
    id: root
    moduleName: "paweltkaczyk.browser-router"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "󰖟"
        slotSize: Style.bar.statusSlot
        tooltipText: "Browser Router"
        onPressed: Quickshell.execDetached(["omarchy-browser-router", "settings"])
    }
}
