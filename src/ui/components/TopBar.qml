import QtQuick 2.15
import QtQuick.Controls 2.15
import theme 1.0

// Bandeau supérieur : logo/mascotte, titre,
// indicateur système. Le téléchargement des modèles est placé dans Main.qml,
// en haut à droite de la fenêtre.
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
                        assistant.modelsInstalled
                            ? Theme.colorListening
                            : Theme.textSecondary

                    anchors.verticalCenter:
                        parent.verticalCenter
                }

                Text {
                    text:
                        assistant.modelsInstalled
                            ? "SYSTÈME EN LIGNE"
                            : "MODÈLES VOCAUX NON INSTALLÉS"

                    color: Theme.textSecondary

                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.letterSpacing: 2
                }
            }
        }

    }
}
