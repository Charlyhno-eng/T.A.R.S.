import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0

Dialog {
    id: root
    objectName: "shortcutDialog"

    property string candidate: ""
    property bool english: assistant.language === "en"

    width: Math.min(parent.width - 48, 420)
    modal: true
    padding: 24
    closePolicy: Popup.CloseOnEscape
    onOpened: {
        candidate = ""
        desktop.beginShortcutCapture()
        captureArea.forceActiveFocus()
    }
    onClosed: desktop.endShortcutCapture()

    background: Rectangle {
        radius: 18
        color: Theme.panelBackground
        border.width: 1
        border.color: Theme.panelBorder
    }

    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.68) }

    contentItem: Column {
        id: captureArea
        spacing: 16
        focus: true

        Keys.onPressed: function(event) {
            event.accepted = true
            if (event.key === Qt.Key_Escape) {
                root.close()
                return
            }
            if (!event.isAutoRepeat) {
                var shortcut = desktop.shortcutFromKey(event.key, event.modifiers)
                if (shortcut.length > 0)
                    root.candidate = shortcut
            }
        }
        Keys.onReleased: function(event) { event.accepted = true }

        Text {
            width: parent.width
            text: root.english ? "Press your shortcut" : "Appuyez sur votre raccourci"
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: 18
            font.bold: true
            wrapMode: Text.WordWrap
        }

        Text {
            width: parent.width
            text: root.english
                ? "Use Ctrl, Alt or Super with a key, or a function key. Hold it to speak, then release to send."
                : "Utilisez Ctrl, Alt ou Super avec une touche, ou une touche de fonction. Maintenez pour parler, puis relâchez pour envoyer."
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }

        Rectangle {
            width: parent.width
            height: 54
            radius: 9
            color: Theme.backgroundTop
            border.color: Theme.colorIdle
            Text {
                anchors.centerIn: parent
                text: root.candidate || (root.english ? "Waiting for keys…" : "En attente des touches…")
                color: Theme.colorIdle
                font.family: Theme.fontFamily
                font.pixelSize: 16
            }
            MouseArea {
                anchors.fill: parent
                onClicked: captureArea.forceActiveFocus()
            }
        }

        Text {
            width: parent.width
            visible: text.length > 0
            text: desktop.shortcutError
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }

        Row {
            spacing: 12
            SettingsButton {
                primary: true
                text: root.english ? "Save shortcut" : "Enregistrer"
                enabled: root.candidate.length > 0
                onClicked: {
                    if (desktop.saveShortcut(root.candidate))
                        root.close()
                }
            }
            SettingsButton {
                text: root.english ? "Cancel" : "Annuler"
                onClicked: root.close()
            }
        }
    }
}
