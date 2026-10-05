import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15
import QtQuick.Layouts 1.15
import theme 1.0
import "components"

ApplicationWindow {
    id: window

    width: 1000
    height: 700

    minimumWidth: 600
    minimumHeight: 560

    visible: false
    flags: Qt.Window | Qt.FramelessWindowHint

    onClosing: function(close) {
        settingsDialog.close()
        conversationDialog.close()
        if (desktop.hideToTray())
            close.accepted = false
    }

    title: "T.A.R.S. — Assistant"

    color: "transparent"

    property string assistantState:
        assistant.state

    readonly property bool compact: width < 900 || height < 640
    readonly property bool showConversation: width >= 960 && height >= 640
    readonly property bool showReadiness: width >= 1450 && height >= 760
    readonly property real textScale: Math.min(1.4, Math.max(0.9, Math.min(width / 1000, height / 700)))
    readonly property real outerMargin: Math.min(40, Math.max(20, width * 0.025))

    background: FrostedBackground {
    }

    MouseArea {
        anchors.top: parent.top
        width: parent.width
        height: 84
        enabled: window.visibility !== Window.FullScreen
        onPressed: window.startSystemMove()
    }

    Canvas {
        anchors.fill: parent
        opacity: 0.045

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            var ctx = getContext("2d")

            ctx.reset()

            ctx.strokeStyle =
                Theme.accentCyan

            ctx.lineWidth = 1

            var step = 48

            for (
                var x = 0;
                x < width;
                x += step
            ) {
                ctx.beginPath()
                ctx.moveTo(x, 0)
                ctx.lineTo(x, height)
                ctx.stroke()
            }

            for (
                var y = 0;
                y < height;
                y += step
            ) {
                ctx.beginPath()
                ctx.moveTo(0, y)
                ctx.lineTo(width, y)
                ctx.stroke()
            }
        }
    }

    TopBar {
        id: topBar

        anchors.top: parent.top
        anchors.left: parent.left

        anchors.margins: window.outerMargin
        width: Math.min(420, settingsButton.x - window.outerMargin - (clockDisplay.visible ? 120 : 20))
    }

    ToolButton {
        id: closeButton
        objectName: "closeWindowButton"
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: 20
        anchors.rightMargin: 24
        width: 42
        height: 42
        text: "×"
        Accessible.name: assistant.language === "en" ? "Close window" : "Fermer la fenêtre"
        onClicked: window.close()

        contentItem: Text {
            text: closeButton.text
            color: Theme.textPrimary
            font.pixelSize: 28
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 21
            color: closeButton.hovered || closeButton.down ? Theme.panelBorder : "transparent"
        }
        ToolTip.visible: hovered
        ToolTip.delay: 500
        ToolTip.text: Accessible.name
    }

    Rectangle {
        id: settingsButton
        anchors.top: parent.top
        anchors.right: closeButton.left
        anchors.topMargin: 20
        anchors.rightMargin: 16
        width: 42
        height: 42
        radius: 21
        color: settingsMouse.containsMouse ? Theme.panelBorder : "transparent"
        border.width: 1
        border.color: Theme.panelBorder

        Text {
            anchors.centerIn: parent
            text: "⚙"
            color: Theme.textPrimary
            font.pixelSize: 25
        }
        MouseArea {
            id: settingsMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: settingsDialog.open()
        }
        ToolTip.visible: settingsMouse.containsMouse
        ToolTip.text: assistant.language === "en" ? "Settings" : "Paramètres"
    }

    SettingsDialog {
        id: settingsDialog
        anchors.centerIn: parent
    }

    Text {
        id: clockDisplay
        anchors.top: parent.top
        anchors.right: settingsButton.left

        anchors.topMargin: 33
        anchors.rightMargin: 16

        visible:
            window.width >= 760 && !assistant.modelsDownloading

        text: Qt.formatDateTime(
            clock.now,
            "hh:mm:ss"
        )

        color:
            Theme.textSecondary

        font.family:
            Theme.fontFamily

        font.pixelSize: 13

        font.letterSpacing: 1

        QtObject {
            id: clock

            property date now:
                new Date()
        }

        Timer {
            interval: 1000

            running: true
            repeat: true

            onTriggered: {
                clock.now = new Date()
            }
        }
    }

    RowLayout {
        id: workspace
        anchors.top: parent.top
        anchors.bottom: footer.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: window.compact ? 100 : 110
        anchors.bottomMargin: 20
        anchors.leftMargin: window.outerMargin
        anchors.rightMargin: window.outerMargin
        spacing: 28 * window.textScale

        ReadinessPanel {
            objectName: "readinessPanel"
            visible: window.showReadiness
            Layout.preferredWidth: Math.min(340, window.width * 0.2)
            Layout.fillHeight: true
            textScale: window.textScale
            onSettingsRequested: settingsDialog.open()
        }

        Item {
            id: robotColumn
            Layout.fillWidth: true
            Layout.fillHeight: true

            Text {
                id: tagline
                anchors.top: parent.top
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                visible: !window.compact
                text: assistant.language === "en" ? "YOUR LOCAL VOICE ASSISTANT" : "VOTRE ASSISTANT VOCAL LOCAL"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: 11 * window.textScale
                font.letterSpacing: 2
                elide: Text.ElideRight
            }
            Text {
                id: greeting
                anchors.top: parent.top
                anchors.topMargin: window.compact ? 0 : tagline.height + 14
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: assistant.language === "en" ? "How can I help?" : "Comment puis-je aider ?"
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: 28 * window.textScale
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Item {
                id: centralItem
                anchors.top: greeting.bottom
                anchors.bottom: caption.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.topMargin: 14
                anchors.bottomMargin: 14

                JarvisSphere {
                    id: sphere
                    objectName: "assistantRobot"
                    anchors.centerIn: parent
                    width: Math.max(0, Math.min(parent.width, parent.height))
                    height: width
                    sphereState: window.assistantState
                    animationsEnabled: window.active
                    interactionEnabled: assistant.modelsReady && !assistant.modelsDownloading
                    onPressed: assistant.startListening()
                    onReleased: assistant.stopListening()
                }
            }
            Text {
                id: caption
                anchors.bottom: downloadProgress.visible ? downloadProgress.top : parent.bottom
                anchors.bottomMargin: downloadProgress.visible ? 14 : 0
                width: parent.width
                text: {
                    var english = assistant.language === "en"
                    if (assistant.modelsDownloading)
                        return assistant.status
                    if (assistant.modelsLoading)
                        return english ? "Preparing your local voice models…" : "Préparation de vos modèles vocaux locaux…"
                    if (!assistant.modelsInstalled)
                        return english ? "Click the model status to install voices" : "Cliquez sur le statut des modèles pour installer les voix"
                    if (!assistant.modelsReady)
                        return assistant.status
                    if (window.assistantState === "idle") {
                        if (!window.showConversation && assistant.transcript)
                            return assistant.transcript
                        return english ? "Hold T.A.R.S. to speak" : "Maintenez T.A.R.S. pour parler"
                    }
                    if (!window.showConversation && assistant.response)
                        return "T.A.R.S.: " + assistant.response
                    return assistant.status
                }
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: 13 * window.textScale
                font.letterSpacing: 0.2
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                maximumLineCount: 3
                elide: Text.ElideRight
            }
            ProgressBar {
                id: downloadProgress
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(260, parent.width)
                height: 4
                visible: assistant.modelsDownloading
                indeterminate: visible && window.active
            }
        }

        ConversationPanel {
            objectName: "conversationPanel"
            visible: window.showConversation
            Layout.preferredWidth: Math.min(480, window.width * 0.32)
            Layout.fillHeight: true
            textScale: window.textScale
        }
    }

    Rectangle {
        id: footer
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: window.outerMargin
        width: Math.min(parent.width - 2 * window.outerMargin, footerContent.implicitWidth + 32)
        height: 64 * window.textScale
        radius: 16
        color: Qt.rgba(0.06, 0.10, 0.17, 0.92)
        border.color: Qt.rgba(0.51, 0.60, 0.74, 0.18)

        RowLayout {
            id: footerContent
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            anchors.topMargin: 10
            anchors.bottomMargin: 10
            spacing: 16 * window.textScale
            StatusPanel {
                id: statusPanel
                Layout.alignment: Qt.AlignVCenter
                sphereState: window.assistantState
                language: assistant.language
                textScale: window.textScale
                label: assistant.modelsDownloading
                    ? (language === "en" ? "INSTALLING" : "INSTALLATION")
                    : assistant.modelsLoading
                        ? (language === "en" ? "WARMING UP" : "PRÉPARATION")
                        : !assistant.modelsReady
                            ? (language === "en" ? "SETUP NEEDED" : "À CONFIGURER")
                            : Theme.stateLabel(sphereState, language)
                accent: assistant.modelsReady ? Theme.stateColor(sphereState) : Theme.textSecondary
            }

            Rectangle {
                visible: !window.compact
                Layout.preferredWidth: 1
                Layout.preferredHeight: 24
                color: Theme.panelBorder
            }

            Button {
                id: shortcutButton
                visible: !window.compact
                Layout.preferredWidth: shortcutContent.implicitWidth + 20
                Layout.fillWidth: true
                implicitHeight: 36 * window.textScale
                text: !desktop.shortcutSupported
                    ? (assistant.language === "en" ? "Voice settings" : "Paramètres vocaux")
                    : (desktop.shortcut
                        ? (assistant.language === "en" ? "Hold to speak" : "Maintenez pour parler")
                        : (assistant.language === "en" ? "Set a voice shortcut" : "Définir un raccourci vocal"))
                Accessible.name: text + (desktop.shortcutSupported && desktop.shortcut ? " " + desktop.shortcut : "")
                contentItem: RowLayout {
                    id: shortcutContent
                    spacing: 12
                    Text {
                        Layout.fillWidth: true
                        text: shortcutButton.text
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pixelSize: 12 * window.textScale
                        elide: Text.ElideRight
                    }
                    Rectangle {
                        visible: desktop.shortcutSupported && !!desktop.shortcut
                        implicitWidth: shortcutKey.implicitWidth + 18
                        implicitHeight: 28 * window.textScale
                        radius: 6
                        color: Qt.rgba(0.51, 0.60, 0.74, 0.10)
                        border.color: Theme.panelBorder
                        Text {
                            id: shortcutKey
                            anchors.centerIn: parent
                            text: desktop.shortcut
                            color: Theme.textPrimary
                            font.family: Theme.fontFamily
                            font.pixelSize: 11 * window.textScale
                            font.weight: Font.DemiBold
                        }
                    }
                }
                background: Rectangle {
                    radius: 8
                    color: shortcutButton.down ? Theme.panelBorder
                        : shortcutButton.hovered ? Qt.rgba(0.51, 0.60, 0.74, 0.08) : "transparent"
                    border.width: shortcutButton.activeFocus ? 1 : 0
                    border.color: Theme.accentCyan
                }
                onClicked: settingsDialog.open()
                ToolTip.visible: hovered
                ToolTip.text: assistant.language === "en"
                    ? "Configure hold-to-talk in Settings to speak while T.A.R.S. is hidden."
                    : "Configurez un raccourci dans les paramètres pour parler lorsque T.A.R.S. est masqué."
            }
            SettingsButton {
                objectName: "openConversationButton"
                visible: !window.showConversation
                text: "Conversation"
                onClicked: conversationDialog.open()
            }
        }
    }

    Dialog {
        id: conversationDialog
        objectName: "conversationDialog"
        anchors.centerIn: parent
        width: Math.min(parent.width - 40, 720)
        height: Math.min(parent.height - 40, 760)
        padding: 0
        modal: true
        background: Rectangle { color: Theme.panelBackground; radius: 18 }
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.68) }
        header: Item {
            height: 42
            ToolButton {
                anchors.right: parent.right
                anchors.rightMargin: 12
                text: "×"
                Accessible.name: assistant.language === "en" ? "Close conversation" : "Fermer la conversation"
                onClicked: conversationDialog.close()
                contentItem: Text {
                    text: "×"
                    color: Theme.textPrimary
                    font.pixelSize: 28
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
        contentItem: ConversationPanel { textScale: window.textScale }
    }

    WindowResizeHandles {
        anchors.fill: parent
        targetWindow: window
        enabled: window.visibility === Window.Windowed
        z: 10
    }

}
