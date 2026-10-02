import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0

Rectangle {
    id: root
    property real textScale: 1
    readonly property bool english: assistant.language === "en"
    signal settingsRequested()
    color: Qt.rgba(Theme.panelBackground.r, Theme.panelBackground.g, Theme.panelBackground.b, 0.78)
    radius: 18
    border.color: Theme.panelBorder

    Column {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 24
        spacing: 26
        Text {
            text: root.english ? "READY TO TALK?" : "PRÊT À PARLER ?"
            color: Theme.accentCyan
            font.family: Theme.fontFamily
            font.pixelSize: 12 * root.textScale
            font.bold: true
            font.letterSpacing: 1.5
        }
        Repeater {
            model: [
                { label: root.english ? "LOCAL VOICE" : "VOIX LOCALE",
                  value: assistant.modelsReady ? (root.english ? "Ready" : "Prête")
                    : (assistant.modelsDownloading ? (root.english ? "Downloading…" : "Téléchargement…")
                    : (assistant.modelsLoading ? (root.english ? "Loading…" : "Chargement…")
                    : (root.english ? "Models unavailable" : "Modèles indisponibles"))),
                  detail: root.english ? "Speech recognition and playback run locally."
                    : "Reconnaissance et lecture vocales en local." },
                { label: root.english ? "GLM ACCESS" : "ACCÈS GLM",
                  value: assistant.llmKeyConfigured ? (root.english ? "API key saved" : "Clé API enregistrée")
                    : (root.english ? "Add your API key" : "Ajoutez votre clé API"),
                  detail: root.english ? "Replies need an internet connection."
                    : "Les réponses nécessitent une connexion internet." },
                { label: root.english ? "VOICE LANGUAGE" : "LANGUE VOCALE",
                  value: root.english ? "English" : "Français",
                  detail: root.english ? "Change it in Settings." : "Modifiable dans les paramètres." }
            ]
            Column {
                required property var modelData
                width: parent.width
                spacing: 8
                Text {
                    width: parent.width
                    text: modelData.label
                    color: Theme.textSecondary
                    font.pixelSize: 10 * root.textScale
                    font.letterSpacing: 1.5
                    wrapMode: Text.WordWrap
                }
                Text {
                    width: parent.width
                    text: modelData.value
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: 17 * root.textScale
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                }
                Text {
                    width: parent.width
                    text: modelData.detail
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: 12 * root.textScale
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
    SettingsButton {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 24
        text: root.english ? "Open Settings" : "Ouvrir les paramètres"
        onClicked: root.settingsRequested()
    }
}
