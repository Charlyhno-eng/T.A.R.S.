import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0

// Bandeau supérieur : logo/mascotte, titre,
// indicateur système et bouton d'installation TTS.
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

            Row {
                spacing: 6

                Rectangle {
                    width: 7
                    height: 7

                    radius: 3.5

                    color:
                        assistant.ttsInstalled
                            ? Theme.colorListening
                            : Theme.textSecondary

                    anchors.verticalCenter:
                        parent.verticalCenter
                }

                Text {
                    text:
                        assistant.ttsInstalled
                            ? "SYSTÈME EN LIGNE"
                            : "MOTEUR VOCAL NON INSTALLÉ"

                    color: Theme.textSecondary

                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.letterSpacing: 2
                }
            }
        }

        Item {
            width: 48
            height: 46

            visible:
                !assistant.ttsInstalled ||
                assistant.ttsDownloading

            anchors.verticalCenter:
                parent.verticalCenter

            Rectangle {
                id: downloadButton

                anchors.centerIn: parent

                width: 38
                height: 38

                radius: 19

                color:
                    mouseArea.containsMouse
                        ? Theme.panelBorder
                        : "transparent"

                border.width: 1

                border.color:
                    assistant.ttsDownloading
                        ? Theme.colorListening
                        : Theme.panelBorder

                Behavior on color {
                    ColorAnimation {
                        duration: Theme.animFast
                    }
                }

                Behavior on border.color {
                    ColorAnimation {
                        duration: Theme.animFast
                    }
                }

                Text {
                    anchors.centerIn: parent

                    text:
                        assistant.ttsDownloading
                            ? "..."
                            : "↓"

                    color:
                        assistant.ttsDownloading
                            ? Theme.colorListening
                            : Theme.textPrimary

                    font.family: Theme.fontFamily
                    font.pixelSize:
                        assistant.ttsDownloading ? 14 : 23
                    font.bold: true

                    verticalAlignment:
                        Text.AlignVCenter

                    horizontalAlignment:
                        Text.AlignHCenter
                }

                MouseArea {
                    id: mouseArea

                    anchors.fill: parent

                    hoverEnabled: true

                    enabled:
                        !assistant.ttsInstalled &&
                        !assistant.ttsDownloading

                    cursorShape:
                        enabled
                            ? Qt.PointingHandCursor
                            : Qt.ArrowCursor

                    onClicked: {
                        assistant.downloadTts()
                    }
                }

                ToolTip.visible:
                    mouseArea.containsMouse &&
                    mouseArea.enabled

                ToolTip.text:
                    "Télécharger le moteur vocal pour une utilisation hors ligne"

                ToolTip.delay: 500
            }
        }
    }
}
