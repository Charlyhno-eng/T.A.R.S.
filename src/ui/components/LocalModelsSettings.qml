import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0

Column {
    id: root
    spacing: 10
    readonly property bool english: assistant.language === "en"
    readonly property bool busy: assistant.modelsDownloading || assistant.modelsLoading

    Text {
        text: root.english ? "LOCAL MODELS" : "MODÈLES LOCAUX"
        color: Theme.colorIdle
        font.family: Theme.fontFamily
        font.pixelSize: 11
        font.bold: true
        font.letterSpacing: 2
    }

    Text {
        width: parent.width
        text: root.english
            ? "Download the voice for the language selected above and speech recognition. Both work offline after installation."
            : "Téléchargez la voix pour la langue choisie ci-dessus et la reconnaissance vocale. Elles fonctionnent ensuite hors ligne."
        wrapMode: Text.WordWrap
        color: Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: 12
    }

    Text {
        objectName: "ttsModelStatus"
        width: parent.width
        text: "Piper TTS · " + (root.english ? "English" : "Français") + " — "
            + (assistant.ttsInstalled
                ? (root.english ? "Installed" : "Installée")
                : (root.english ? "Download required (~63 MB)" : "À télécharger (~63 Mo)"))
        wrapMode: Text.WordWrap
        color: assistant.ttsInstalled ? Theme.colorIdle : Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: 12
    }

    Text {
        objectName: "sttModelStatus"
        width: parent.width
        text: "Parakeet — " + (assistant.sttInstalled
            ? (root.english ? "Installed" : "Installé")
            : (root.english ? "Download required (~2.5 GB)" : "À télécharger (~2,5 Go)"))
        wrapMode: Text.WordWrap
        color: assistant.sttInstalled ? Theme.colorIdle : Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: 12
    }

    SettingsButton {
        objectName: "downloadModelsButton"
        width: parent.width
        primary: !assistant.modelsInstalled
        text: assistant.modelsDownloading
            ? (root.english ? "Downloading models…" : "Téléchargement en cours…")
            : (assistant.modelsLoading
                ? (root.english ? "Loading models…" : "Chargement en cours…")
                : (assistant.modelsInstalled
                    ? (root.english ? "Models installed" : "Modèles installés")
                    : (root.english ? "Download missing models" : "Télécharger les modèles manquants")))
        enabled: !assistant.modelsInstalled && !root.busy && assistant.state === "idle"
        onClicked: assistant.downloadModels()
    }

    Text {
        objectName: "modelDownloadStatus"
        width: parent.width
        visible: root.busy || !assistant.modelsInstalled
        text: assistant.status
        wrapMode: Text.WordWrap
        color: root.busy ? Theme.colorListening : Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: 12
    }
}
