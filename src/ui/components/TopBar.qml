import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0

Item {
    id: root

    width: contentRow.width
    height: 46

    Row {
        id: contentRow

        spacing: 14

        height: 46

        Image {
            source: "../../../assets/tars-mascot.png"

            width: 40
            height: 40

            fillMode: Image.PreserveAspectFit

            anchors.verticalCenter:
                parent.verticalCenter

            visible:
                status === Image.Ready
        }

        Column {
            anchors.verticalCenter:
                parent.verticalCenter

            spacing: 2

            Text {
                text: "T.A.R.S."

                color: Theme.textPrimary

                font.family: Theme.fontFamily
                font.pixelSize: 20
                font.bold: true
                font.letterSpacing: 3
            }

            Item {
                id: systemStatus
                width: statusRow.implicitWidth
                height: statusRow.implicitHeight

                Row {
                    id: statusRow
                    spacing: 6

                    Rectangle {
                        width: 7
                        height: 7

                        radius: 3.5

                        color: assistant.modelsDownloading || assistant.modelsLoading || assistant.modelsReady
                            ? Theme.colorListening : Theme.textSecondary

                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Text {
                        text: assistant.modelsDownloading
                            ? (assistant.language === "en" ? "DOWNLOADING LOCAL MODELS" : "TÉLÉCHARGEMENT DES MODÈLES")
                            : (assistant.modelsLoading
                                ? (assistant.language === "en" ? "LOADING LOCAL MODELS" : "CHARGEMENT DES MODÈLES LOCAUX")
                                : (assistant.modelsReady
                                    ? (assistant.language === "en" ? "SYSTEM ONLINE" : "SYSTÈME EN LIGNE")
                                    : (assistant.language === "en"
                                        ? "LOCAL MODELS NOT INSTALLED"
                                        : "MODÈLES LOCAUX NON INSTALLÉS")))

                        color: assistant.modelsDownloading || assistant.modelsLoading
                            ? Theme.colorListening : Theme.textSecondary

                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        font.letterSpacing: 2
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: !assistant.modelsInstalled && !assistant.modelsDownloading && !assistant.modelsLoading
                    hoverEnabled: enabled
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: assistant.downloadModels()

                    ToolTip.visible: enabled && containsMouse
                    ToolTip.delay: 500
                    ToolTip.text: assistant.language === "en"
                        ? "Download Pocket TTS and Parakeet"
                        : "Télécharger Pocket TTS et Parakeet"
                }
            }
        }

    }
}
