import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import theme 1.0

Dialog {
    id: root
    objectName: "exportDialog"
    property bool english: assistant.language === "en"
    width: Math.min(parent.width - 48, 520)
    height: Math.min(parent.height - 48, 430)
    modal: true
    padding: 24
    onOpened: target.currentIndex = exporter.platform === "windows" ? 1 : (exporter.platform === "macos" ? 2 : 0)

    background: Rectangle {
        radius: 18
        color: Theme.panelBackground
        border.color: Theme.panelBorder
    }
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.68) }

    contentItem: ColumnLayout {
        spacing: 14
        Text {
            text: root.english ? "Export application" : "Exporter l'application"
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: 18
            font.bold: true
        }
        ComboBox {
            id: target
            objectName: "exportTarget"
            Layout.fillWidth: true
            model: ["Linux", "Windows", "macOS"]
            property string selectedPlatform: ["linux", "windows", "macos"][currentIndex]
            enabled: !exporter.running
        }
        Text {
            Layout.fillWidth: true
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: 12
            wrapMode: Text.WordWrap
            text: target.selectedPlatform !== exporter.platform
                ? (root.english ? "Run the export on the selected operating system." : "Lancez l'export sur le système d'exploitation sélectionné.")
                : (!exporter.toolsAvailable
                    ? (root.english ? "Install export tools with: uv sync --group build" : "Installez les outils d'export avec : uv sync --group build")
                    : (root.english
                        ? "Choose a destination. Export includes the application and its dependencies. Your settings, API key and downloaded models stay on this computer."
                        : "Choisissez une destination. L'export inclut l'application et ses dépendances. Vos réglages, votre clé API et les modèles téléchargés restent sur cet ordinateur."))
        }
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 60
            clip: true
            TextArea {
                text: exporter.log
                readOnly: true
                wrapMode: TextEdit.WrapAnywhere
                color: Theme.textSecondary
                font.family: "monospace"
                font.pixelSize: 10
                background: Rectangle { color: Theme.backgroundTop; radius: 8 }
            }
        }
        Row {
            spacing: 12
            SettingsButton {
                primary: true
                text: exporter.running ? (root.english ? "Exporting…" : "Export en cours…") : (root.english ? "Export…" : "Exporter…")
                enabled: !exporter.running && exporter.toolsAvailable && target.selectedPlatform === exporter.platform
                onClicked: exporter.start(target.selectedPlatform)
            }
            SettingsButton {
                text: root.english ? "Close" : "Fermer"
                onClicked: root.close()
            }
        }
    }
}
