pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import qs.Ui as Ui

Item {
    id: root
    property var shell: null
    property var state: ({
            config: {
                rules: [],
                fallback: "system"
            },
            targets: [],
            pending: []
        })
    property string message: ""
    property bool picker: state.pending && state.pending.length > 0
    property string editId: ""
    property int editIndex: -1
    property var jobs: []
    property string testResult: ""
    property string chosenTarget: ""
    property bool showSettings: false
    property alias previewItem: content
    readonly property string backend: decodeURIComponent(String(Qt.resolvedUrl("bin/omarchy-browser-router")).replace(/^file:\/\//, ""))
    readonly property var request: picker ? state.pending[0] : null
    readonly property var fallbackOptions: [
        {
            value: "system",
            label: strings.t("system")
        }
    ].concat(state.targets.map(function (t) {
        return {
            value: t.id,
            label: root.safe(t.label)
        };
    }))
    readonly property var ruleOptions: [
        {
            value: "ask",
            label: strings.t("ask")
        }
    ].concat(fallbackOptions)

    Commons.Translations {
        id: strings
        directory: Qt.resolvedUrl("i18n")
    }

    // Local escaping protects strings sent to host components on older shells
    // whose text labels might still use Text.AutoText. Our own text is PlainText.
    function safe(value) {
        return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
    function targetLabel(id) {
        if (id === "ask")
            return strings.t("ask");
        if (id === "system")
            return strings.t("system");
        for (var i = 0; i < state.targets.length; i++)
            if (state.targets[i].id === id)
                return state.targets[i].label;
        return strings.t("unavailable");
    }
    function call(args) {
        jobs = jobs.concat([args]);
        startNext();
    }
    function startNext() {
        if (worker.running || jobs.length === 0)
            return;
        var next = jobs[0];
        jobs = jobs.slice(1);
        worker.command = [backend].concat(next);
        worker.running = true;
    }
    function action(name, payload) {
        call(["action", name, JSON.stringify(payload || {})]);
    }
    function refresh() {
        call(["snapshot"]);
    }
    function open(payloadJson) {
        window.visible = true;
        refresh();
    }
    function close() {
        window.visible = false;
    }
    function requestClose() {
        // Closing keeps queued links until explicitly opened/cancelled.
        if (shell && shell.hide)
            shell.hide("paweltkaczyk.browser-router");
        else
            close();
    }
    function saveRule() {
        var payload = {
            pattern: pattern.text,
            target: destination.value
        };
        if (editId) {
            payload.id = editId;
            payload.index = editIndex;
        }
        action("rule", payload);
    }
    function editRule(rule, index) {
        editId = rule.id;
        editIndex = index;
        pattern.text = rule.pattern;
        destination.value = rule.target;
    }
    function clearEditor() {
        editId = "";
        editIndex = -1;
        pattern.text = "";
        destination.value = "ask";
    }

    Process {
        id: worker
        property string output: ""
        stdout: StdioCollector {
            onStreamFinished: worker.output = text
        }
        onExited: function (code, status) {
            try {
                var data = JSON.parse(output);
                if (data.error)
                    root.message = data.error;
                else if (Array.isArray(data)) {
                    root.testResult = data.map(function (d) {
                        return (d.rule || strings.t("fallback")) + " → " + d.label;
                    }).join("\n");
                } else {
                    root.state = data;
                    root.message = "";
                    if (!root.chosenTarget || !data.targets.some(function (t) {
                        return t.id === root.chosenTarget;
                    }))
                        root.chosenTarget = data.targets.length ? data.targets[0].id : "";
                    // Only clear a successfully saved rule, not another action.
                    if (command[1] === "action" && command[2] === "rule")
                        root.clearEditor();
                }
            } catch (e) {
                root.message = strings.t("backendError");
            }
            output = "";
            Qt.callLater(root.startNext);
        }
    }

    FloatingWindow {
        id: window
        visible: false
        title: "Browser Router"
        implicitWidth: Commons.Style.space(620)
        implicitHeight: Commons.Style.space(root.picker && !root.showSettings ? 350 : 690)
        color: Commons.Color.background
        onVisibleChanged: if (visible)
            Qt.callLater(function () {
                content.forceActiveFocus();
            })

        FocusScope {
            id: content
            anchors.fill: parent
            focus: true
            LayoutMirroring.enabled: Commons.I18n.rightToLeft
            LayoutMirroring.childrenInherit: true
            Keys.onEscapePressed: root.requestClose()

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Commons.Style.space(20)
                spacing: Commons.Style.space(12)

                RowLayout {
                    Layout.fillWidth: true
                    PlainText {
                        text: root.picker ? strings.t("chooseTitle") : strings.t("title")
                        font.pixelSize: Commons.Style.font.heading
                        font.bold: true
                        Layout.fillWidth: true
                    }
                    Ui.Button {
                        text: strings.t("refresh")
                        focusable: true
                        onClicked: root.refresh()
                    }
                    Ui.Button {
                        text: strings.t("close")
                        focusable: true
                        onClicked: root.requestClose()
                    }
                }

                PlainText {
                    visible: root.message !== ""
                    text: root.message
                    color: Commons.Color.urgent
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }

                Controls.ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentWidth: availableWidth
                    clip: true

                    ColumnLayout {
                        width: parent.width
                        spacing: Commons.Style.space(14)

                        ColumnLayout {
                            visible: root.picker
                            Layout.fillWidth: true
                            spacing: Commons.Style.space(10)
                            PlainText {
                                Layout.fillWidth: true
                                text: root.request ? root.request.url : ""
                                wrapMode: Text.WrapAnywhere
                                maximumLineCount: 3
                                elide: Text.ElideRight
                            }
                            PlainText {
                                text: root.request && root.request.private ? strings.t("private") : strings.t("queued").arg(Commons.I18n.formatNumber(root.state.pending.length))
                            }
                            Ui.Dropdown {
                                id: pickerTarget
                                Layout.fillWidth: true
                                label: strings.t("destination")
                                options: root.state.targets.map(function (t) {
                                    return {
                                        value: t.id,
                                        label: root.safe(t.label)
                                    };
                                })
                                value: root.chosenTarget
                                onChanged: function (value) {
                                    root.chosenTarget = value;
                                }
                            }
                            RowLayout {
                                Ui.Button {
                                    text: strings.t("openOnce")
                                    focusable: true
                                    enabled: !!root.chosenTarget && !worker.running
                                    onClicked: root.action("choose", {
                                        id: root.request.id,
                                        target: root.chosenTarget
                                    })
                                }
                                Ui.Button {
                                    text: strings.t("always")
                                    focusable: true
                                    enabled: !!root.chosenTarget && !worker.running
                                    onClicked: root.action("choose", {
                                        id: root.request.id,
                                        target: root.chosenTarget,
                                        remember: true
                                    })
                                }
                                Ui.Button {
                                    text: strings.t("skip")
                                    focusable: true
                                    enabled: !worker.running
                                    onClicked: root.action("cancel", {
                                        id: root.request.id
                                    })
                                }
                            }
                            Ui.Button {
                                text: root.showSettings ? strings.t("hideSettings") : strings.t("manageRules")
                                focusable: true
                                onClicked: root.showSettings = !root.showSettings
                            }
                            Ui.PanelSeparator {
                                Layout.fillWidth: true
                            }
                        }

                        ColumnLayout {
                            visible: !root.picker || root.showSettings
                            Layout.fillWidth: true
                            spacing: Commons.Style.space(14)
                            RowLayout {
                                Layout.fillWidth: true
                                PlainText {
                                    Layout.fillWidth: true
                                    text: root.state.active ? strings.t("active") : strings.t("inactive")
                                    wrapMode: Text.Wrap
                                }
                                Ui.Button {
                                    text: root.state.active ? strings.t("disable") : strings.t("enable")
                                    focusable: true
                                    enabled: !worker.running
                                    onClicked: root.action(root.state.active ? "deactivate" : "activate", {})
                                }
                            }
                            Ui.Dropdown {
                                Layout.fillWidth: true
                                label: strings.t("fallback")
                                value: root.state.config.fallback || "system"
                                options: root.fallbackOptions
                                onChanged: function (value) {
                                    root.action("fallback", {
                                        target: value
                                    });
                                }
                            }
                            PlainText {
                                Layout.fillWidth: true
                                text: strings.t("systemHint").arg(root.state.systemBrowser || "—")
                                wrapMode: Text.Wrap
                            }
                            Ui.Button {
                                text: root.state.config.paused ? strings.t("resume") : strings.t("pause")
                                focusable: true
                                onClicked: root.action("pause", {
                                    paused: !root.state.config.paused
                                })
                            }
                            Ui.PanelSeparator {
                                Layout.fillWidth: true
                            }
                            PlainText {
                                text: strings.t("rules")
                                font.bold: true
                            }
                            PlainText {
                                Layout.fillWidth: true
                                text: strings.t("ruleHint")
                                wrapMode: Text.Wrap
                            }
                            Repeater {
                                model: root.state.config.rules
                                delegate: ColumnLayout {
                                    id: ruleRow
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    spacing: Commons.Style.space(4)
                                    PlainText {
                                        Layout.fillWidth: true
                                        text: ruleRow.modelData.pattern
                                        elide: Text.ElideRight
                                        font.bold: true
                                    }
                                    PlainText {
                                        Layout.fillWidth: true
                                        text: root.targetLabel(ruleRow.modelData.target)
                                        elide: Text.ElideRight
                                    }
                                    RowLayout {
                                        Ui.Button {
                                            text: strings.t("edit")
                                            focusable: true
                                            onClicked: root.editRule(ruleRow.modelData, ruleRow.index)
                                        }
                                        Ui.Button {
                                            text: "↑"
                                            focusable: true
                                            enabled: ruleRow.index > 0
                                            onClicked: root.action("move", {
                                                id: ruleRow.modelData.id,
                                                delta: -1
                                            })
                                        }
                                        Ui.Button {
                                            text: "↓"
                                            focusable: true
                                            enabled: ruleRow.index < root.state.config.rules.length - 1
                                            onClicked: root.action("move", {
                                                id: ruleRow.modelData.id,
                                                delta: 1
                                            })
                                        }
                                        Ui.Button {
                                            text: strings.t("delete")
                                            focusable: true
                                            onClicked: root.action("delete", {
                                                id: ruleRow.modelData.id
                                            })
                                        }
                                    }
                                }
                            }
                            PlainText {
                                visible: root.state.config.rules.length === 0
                                text: strings.t("empty")
                            }
                            Ui.TextField {
                                id: pattern
                                Layout.fillWidth: true
                                placeholderText: "github.com/company  ·  *.example.com"
                                maximumLength: 4096
                                onAccepted: root.saveRule()
                            }
                            Ui.Dropdown {
                                id: destination
                                Layout.fillWidth: true
                                label: strings.t("destination")
                                value: "ask"
                                options: root.ruleOptions
                                onChanged: function (value) {
                                    destination.value = value;
                                }
                            }
                            RowLayout {
                                Ui.Button {
                                    text: root.editId ? strings.t("save") : strings.t("add")
                                    enabled: pattern.text.trim().length > 0 && !worker.running
                                    focusable: true
                                    onClicked: root.saveRule()
                                }
                                Ui.Button {
                                    visible: !!root.editId
                                    text: strings.t("cancel")
                                    focusable: true
                                    onClicked: root.clearEditor()
                                }
                            }
                            Ui.PanelSeparator {
                                Layout.fillWidth: true
                            }
                            PlainText {
                                text: strings.t("testTitle")
                                font.bold: true
                            }
                            Ui.TextField {
                                id: testUrl
                                Layout.fillWidth: true
                                placeholderText: "https://github.com/company/project"
                                maximumLength: 16384
                                onAccepted: root.call(["test", text])
                            }
                            Ui.Button {
                                text: strings.t("test")
                                focusable: true
                                enabled: testUrl.text.length > 0 && !worker.running
                                onClicked: root.call(["test", testUrl.text])
                            }
                            PlainText {
                                Layout.fillWidth: true
                                text: root.testResult
                                wrapMode: Text.Wrap
                            }
                            PlainText {
                                Layout.fillWidth: true
                                text: strings.t("scope")
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }
            }
        }
    }
}
